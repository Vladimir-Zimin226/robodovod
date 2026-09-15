import { clamp } from './core/math.js';
import { circleIntersectsSolid } from './editor/collisions.js';
import { planGridPath } from './navigation.js';

const CAMERA_RADIUS = .24;
const SHOT_SECONDS = 7;
const EVENT_SECONDS = 5;

function copyPosition(position) {
  return position.map(Number);
}

function angleDelta(current, target) {
  return Math.atan2(Math.sin(target - current), Math.cos(target - current));
}

function lookAngles(position, target) {
  const dx = target[0] - position[0];
  const dy = target[1] - position[1];
  const dz = target[2] - position[2];
  return {
    yaw: Math.atan2(dx, -dz),
    pitch: clamp(Math.atan2(dy, Math.max(.001, Math.hypot(dx, dz))), -1.25, 1.25)
  };
}

export function cameraPointBlocked(position, solids, radius = CAMERA_RADIUS) {
  return solids.some(solid => {
    const centerY = solid.position[1] || 0;
    const halfHeight = (solid.scale[1] || 0) / 2;
    if (position[1] < centerY - halfHeight - radius || position[1] > centerY + halfHeight + radius) return false;
    return circleIntersectsSolid(position[0], position[2], radius, solid);
  });
}

function segmentClear(from, to, solids) {
  const distance = Math.hypot(to[0] - from[0], to[1] - from[1], to[2] - from[2]);
  const steps = Math.max(1, Math.ceil(distance / .3));
  for (let step = 1; step <= steps; step += 1) {
    const amount = step / steps;
    const point = from.map((value, index) => value + (to[index] - value) * amount);
    if (cameraPointBlocked(point, solids)) return false;
  }
  return true;
}

export function cameraViewClear(position, target, solids) {
  return segmentClear(position, target, solids);
}

function cameraBlockers(scene) {
  const visualRoof = scene.staticObjects.filter(item => item.type === 'roof');
  return [...scene.solids, ...visualRoof];
}

function transitionPath(from, destination, scene) {
  const blockers = cameraBlockers(scene);
  if (segmentClear(from, destination, blockers)) return [copyPosition(destination)];
  const halfWidth = scene.config.width / 2;
  const halfDepth = scene.config.depth / 2;
  const route = planGridPath([from[0], from[2]], [destination[0], destination[2]], {
    step: .65,
    radius: CAMERA_RADIUS,
    solids: scene.solids,
    bounds: { minX: -halfWidth - 14, maxX: halfWidth + 14, minZ: -halfDepth - 16, maxZ: halfDepth + 16 },
    maxIterations: 12000
  });
  if (!route?.length) return [];
  const path = route.map((point, index) => {
    const amount = (index + 1) / route.length;
    return [point[0], from[1] + (destination[1] - from[1]) * amount, point[1]];
  });
  let cursor = from;
  for (const waypoint of path) {
    if (!segmentClear(cursor, waypoint, blockers)) return [];
    cursor = waypoint;
  }
  return path;
}

function robotTarget(robot) {
  return robot ? [robot.position[0], 1.05, robot.position[2]] : [0, 1, 0];
}

function robotCamera(robot, side = 1, distance = 4.2, height = 2.25) {
  const forwardX = Math.sin(robot.yaw);
  const forwardZ = Math.cos(robot.yaw);
  return [
    robot.position[0] - forwardX * distance + forwardZ * side * 2.2,
    height,
    robot.position[2] - forwardZ * distance - forwardX * side * 2.2
  ];
}

function regularShots(scene, simulation) {
  const width = scene.config.width;
  const depth = scene.config.depth;
  const front = scene.layout?.front ?? depth / 2;
  const cross = scene.layout?.crossAisleZ ?? front - 5;
  const robots = simulation.robots;
  const active = robots.filter(robot => robot.activeTask);
  const charging = robots.find(robot => robot.mode === 'charging' || robot.needsCharge);
  const selected = active.length ? active : robots;
  const follow = selected[simulation.trips % Math.max(1, selected.length)];
  const operation = robots.find(robot => robot.pause > 0 && robot.operationType) || follow;
  const process = scene.scenario?.processType;
  const zoneName = scene.scenario?.zoneName || 'рабочей зоны';
  const flowCaption = process === 'cleaning' ? 'Coverage-маршрут уборки' : process === 'palletizing' ? 'Стационарный цикл паллетизации' : process === 'delivery' ? 'Поток клинической доставки' : 'Транспортный поток зоны';
  const shots = [];
  if (follow) shots.push({ id: `follow-${follow.id}`, position: robotCamera(follow, follow.id % 2 ? 1 : -1), target: robotTarget(follow), robotId: follow.id, tracking: { side: follow.id % 2 ? 1 : -1, distance: 4.2, height: 2.25 }, caption: `AMR-${String(follow.id).padStart(2, '0')} выполняет маршрут` });
  shots.push(
    { id: 'exterior', position: [0, 3.4, front + 10], target: [0, 3.1, front], motion: { axis: [1, 0, 0], amplitude: 2.4, speed: .45 }, caption: 'Общий план объекта' },
    { id: 'entrance', position: [0, 1.72, front + 4.6], target: [0, 1.7, cross - 3], motion: { axis: [1, 0, 0], amplitude: 1.1, speed: .5 }, caption: 'Вход в рабочую зону' },
    { id: 'flow-overview', position: [0, 6.35, cross - 2], target: [0, .5, cross - 2.5], motion: { axis: [1, 0, 0], amplitude: 2, speed: .4 }, caption: `${flowCaption} · ${zoneName}` }
  );
  if (operation) shots.push({ id: `operation-${operation.id}`, position: robotCamera(operation, -1, 3.2, 1.9), target: robotTarget(operation), robotId: operation.id, tracking: { side: -1, distance: 3.2, height: 1.9 }, caption: process === 'palletizing' ? 'Рабочий цикл паллетизатора' : process === 'cleaning' ? 'Покрытие участка уборки' : operation.operationType === 'pickup' ? 'Приём груза' : operation.operationType === 'drop' ? 'Передача в зоне назначения' : 'Назначение задания' });
  if (charging) shots.push({ id: `charging-${charging.id}`, position: robotCamera(charging, 1, 3.4, 1.9), target: robotTarget(charging), robotId: charging.id, tracking: { side: 1, distance: 3.4, height: 1.9 }, caption: `AMR-${String(charging.id).padStart(2, '0')} возвращается на зарядку` });
  return shots.filter(shot => !cameraPointBlocked(shot.position, scene.solids));
}

function eventShot(event, scene, simulation) {
  if (!event || event.type === 'system') return null;
  const idMatch = event.message?.match(/AMR-(\d+)/);
  const byId = idMatch ? simulation.robots.find(robot => robot.id === Number(idMatch[1])) : null;
  const robot = byId || simulation.robots.find(candidate => candidate.mode === 'fault')
    || simulation.robots.find(candidate => candidate.blockedByRobot || candidate.reservationBlocked)
    || simulation.robots.find(candidate => candidate.activeTask);
  if (!robot) return null;
  const position = robotCamera(robot, event.type === 'fault' ? -1 : 1, 3.6, 2.1);
  if (cameraPointBlocked(position, scene.solids)) return null;
  return {
    id: `event-${event.type}-${event.id}`,
    position,
    target: robotTarget(robot),
    robotId: robot.id,
    tracking: { side: event.type === 'fault' ? -1 : 1, distance: 3.6, height: 2.1 },
    caption: event.message || 'Событие симуляции',
    event: true
  };
}

export class CameraDirector {
  constructor({ maxSpeed = 6, angularSpeed = 1.5 } = {}) {
    this.position = [0, 2, 0];
    this.yaw = 0;
    this.pitch = 0;
    this.maxSpeed = maxSpeed;
    this.angularSpeed = angularSpeed;
    this.moving = false;
    this.sprinting = false;
    this.flying = true;
    this.mode = 'AUTOPILOT';
    this.active = false;
    this.revisionId = null;
    this.currentShot = null;
    this.shotElapsed = 0;
    this.shotCursor = 0;
    this.lastEventId = 0;
    this.path = [];
    this.history = [];
    this.revisionTransitions = 0;
  }

  reset(scene, simulation, initialPosition = scene.spawn) {
    this.position = copyPosition(initialPosition);
    this.yaw = 0;
    this.pitch = -.03;
    this.mode = 'AUTOPILOT';
    this.active = true;
    this.revisionId = scene.scenario?.revisionId || simulation.revisionId || null;
    this.currentShot = null;
    this.shotElapsed = SHOT_SECONDS;
    this.shotCursor = 0;
    this.lastEventId = simulation.events.at(-1)?.id || 0;
    this.path = [];
    this.history = [];
    this.revisionTransitions = 0;
  }

  suspend() {
    this.active = false;
    this.mode = 'MANUAL_FIRST_PERSON';
  }

  resume(scene, simulation, camera = null) {
    if (camera) {
      this.position = copyPosition(camera.position);
      this.yaw = camera.yaw;
      this.pitch = camera.pitch;
    }
    this.active = true;
    this.mode = 'AUTOPILOT';
    this.shotElapsed = SHOT_SECONDS;
    this.path = [];
    this.adoptRevision(scene, simulation);
  }

  adoptRevision(scene, simulation) {
    const revision = scene.scenario?.revisionId || simulation.revisionId || null;
    if (revision === this.revisionId) return false;
    this.revisionId = revision;
    this.revisionTransitions += 1;
    this.currentShot = null;
    this.shotElapsed = SHOT_SECONDS;
    this.path = [];
    this.lastEventId = simulation.events.at(-1)?.id || 0;
    return true;
  }

  selectShot(scene, simulation, forced = null) {
    const blockers = cameraBlockers(scene);
    const options = (forced ? [forced] : regularShots(scene, simulation))
      .filter(shot => cameraViewClear(shot.position, shot.target, blockers));
    if (!options.length) return false;
    let shot = options[this.shotCursor % options.length];
    if (!forced) {
      this.shotCursor += 1;
      if (shot.id === this.currentShot?.id && options.length > 1) {
        shot = options[this.shotCursor % options.length];
        this.shotCursor += 1;
      }
    }
    const path = transitionPath(this.position, shot.position, scene);
    if (!path.length) return false;
    this.currentShot = { ...shot, target: copyPosition(shot.target) };
    this.path = path;
    this.shotElapsed = 0;
    this.history.push({ id: shot.id, event: Boolean(shot.event), revisionId: this.revisionId });
    if (this.history.length > 200) this.history.shift();
    return true;
  }

  update(delta, scene, simulation) {
    if (!this.active) return this;
    const step = clamp(delta, 0, .1);
    this.adoptRevision(scene, simulation);
    const latestEvent = [...simulation.events].reverse().find(event => event.id > this.lastEventId && event.type !== 'system');
    if (latestEvent) {
      this.lastEventId = latestEvent.id;
      const shot = eventShot(latestEvent, scene, simulation);
      if (shot) this.selectShot(scene, simulation, shot);
    }
    this.shotElapsed += step;
    const duration = this.currentShot?.event ? EVENT_SECONDS : SHOT_SECONDS;
    if (!this.currentShot || this.shotElapsed >= duration) this.selectShot(scene, simulation);

    const waypoint = this.path[0];
    const blockers = cameraBlockers(scene);
    this.moving = false;
    if (waypoint) {
      const dx = waypoint[0] - this.position[0];
      const dy = waypoint[1] - this.position[1];
      const dz = waypoint[2] - this.position[2];
      const distance = Math.hypot(dx, dy, dz);
      const travel = Math.min(distance, this.maxSpeed * step);
      if (distance <= .04) this.path.shift();
      else {
        const candidate = this.position.map((value, index) => value + [dx, dy, dz][index] / distance * travel);
        if (!cameraPointBlocked(candidate, blockers)) {
          this.position = candidate;
          this.moving = travel > .001;
        }
        else this.path = [];
      }
    }

    const tracked = this.currentShot?.robotId
      ? simulation.robots.find(robot => robot.id === this.currentShot.robotId)
      : null;
    const target = tracked ? robotTarget(tracked) : this.currentShot?.target;
    if (tracked && this.currentShot.tracking && !this.path.length) {
      const { side, distance, height } = this.currentShot.tracking;
      const trackingPosition = robotCamera(tracked, side, distance, height);
      if (segmentClear(this.position, trackingPosition, blockers) && cameraViewClear(trackingPosition, target, blockers)) {
        this.path.push(trackingPosition);
      }
    }
    if (!tracked && !this.path.length && this.currentShot?.motion && target) {
      const { axis, amplitude, speed } = this.currentShot.motion;
      const offset = Math.sin(this.shotElapsed * speed) * amplitude;
      const candidate = this.currentShot.position.map((value, index) => value + axis[index] * offset);
      if (!cameraPointBlocked(candidate, blockers) && cameraViewClear(candidate, target, blockers)) {
        const distance = Math.hypot(...candidate.map((value, index) => value - this.position[index]));
        if (distance > .002) {
          const travel = Math.min(distance, this.maxSpeed * step * .38);
          this.position = this.position.map((value, index) => value + (candidate[index] - value) / distance * travel);
          this.moving = true;
        }
      }
    }
    if (target && !this.path.length && !cameraViewClear(this.position, target, blockers)) {
      this.shotElapsed = duration;
    }
    if (target) {
      const desired = lookAngles(this.position, target);
      const angularStep = this.angularSpeed * step;
      this.yaw += clamp(angleDelta(this.yaw, desired.yaw), -angularStep, angularStep);
      this.pitch += clamp(desired.pitch - this.pitch, -angularStep, angularStep);
    }
    return this;
  }

  get caption() {
    return this.currentShot?.caption || '';
  }
}
