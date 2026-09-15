import { circleIntersectsSolid } from './editor/collisions.js';
import { planGridPath } from './navigation.js';

function routeLengths(points) {
  const segments = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    const length = Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]);
    segments.push({ start: total, length });
    total += length;
  }
  return { segments, total };
}

function pointAt(route, distance) {
  const wrapped = ((distance % route.metrics.total) + route.metrics.total) % route.metrics.total;
  let index = route.metrics.segments.findIndex(segment => wrapped <= segment.start + segment.length);
  if (index < 0) index = route.points.length - 2;
  const segment = route.metrics.segments[index];
  const amount = segment.length ? (wrapped - segment.start) / segment.length : 0;
  const a = route.points[index];
  const b = route.points[index + 1];
  return {
    x: a[0] + (b[0] - a[0]) * amount,
    z: a[1] + (b[1] - a[1]) * amount,
    yaw: Math.atan2(b[0] - a[0], b[1] - a[1]),
    segment: index,
    progress: wrapped / route.metrics.total
  };
}

function personHitsSolid(x, z, solids) {
  const radius = .24;
  return solids.some(solid => circleIntersectsSolid(x, z, radius, solid));
}

function lerpAngle(current, target, amount) {
  const difference = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return current + difference * amount;
}

function pointWithOffset(pose, offset) {
  return {
    x: pose.x + Math.cos(pose.yaw) * offset,
    z: pose.z - Math.sin(pose.yaw) * offset
  };
}

function pedestrianClearance(person, x, z, people, robots) {
  let factor = 1;
  let blockedByPerson = false;
  let blockedByRobot = false;
  people.forEach(other => {
    if (other === person) return;
    const distance = Math.min(
      Math.hypot(other.position[0] - x, other.position[2] - z),
      Math.hypot(other.position[0] - person.position[0], other.position[2] - person.position[2])
    );
    if (distance < .48) { factor = 0; blockedByPerson = true; }
    else if (distance < .9) factor = Math.min(factor, (distance - .48) / .42);
  });
  robots.forEach(robot => {
    const distance = Math.min(
      Math.hypot(robot.position[0] - x, robot.position[2] - z),
      Math.hypot(robot.position[0] - person.position[0], robot.position[2] - person.position[2])
    );
    const stopDistance = robot.radius + .27;
    if (distance < stopDistance) { factor = 0; blockedByRobot = true; }
    else if (distance < stopDistance + .55) { factor = Math.min(factor, (distance - stopDistance) / .55); blockedByRobot = true; }
  });
  return { factor: Math.max(0, factor), blockedByPerson, blockedByRobot };
}

function pedestrianMovementCollision(person, x, z, people, robots, solids) {
  const fromX = person.position[0];
  const fromZ = person.position[2];
  const length = Math.hypot(x - fromX, z - fromZ);
  const steps = Math.max(1, Math.ceil(length / .12));
  for (let step = 1; step <= steps; step += 1) {
    const amount = step / steps;
    const sampleX = fromX + (x - fromX) * amount;
    const sampleZ = fromZ + (z - fromZ) * amount;
    if (personHitsSolid(sampleX, sampleZ, solids)) return { type: 'solid' };
    for (const robot of robots) {
      const currentDistance = Math.hypot(robot.position[0] - fromX, robot.position[2] - fromZ);
      const sampleDistance = Math.hypot(robot.position[0] - sampleX, robot.position[2] - sampleZ);
      const minimumDistance = robot.radius + .27;
      if (sampleDistance < minimumDistance && !(currentDistance < minimumDistance && sampleDistance > currentDistance)) return { type: 'robot' };
    }
    for (const other of people) {
      if (other === person) continue;
      const currentDistance = Math.hypot(other.position[0] - fromX, other.position[2] - fromZ);
      const sampleDistance = Math.hypot(other.position[0] - sampleX, other.position[2] - sampleZ);
      if (sampleDistance < .48 && !(currentDistance < .48 && sampleDistance > currentDistance)) return { type: 'person' };
    }
  }
  return null;
}

function updatePeople(simulation, delta, solids, robots) {
  simulation.people.forEach(person => {
    if (person.stationary) {
      person.walking = false;
      person.currentSpeed = 0;
      person.actionPhase += delta * (.35 + person.temperament * .35);
      person.blockedByPerson = false;
      person.blockedByRobot = false;
      person.blockedByObstacle = false;
      return;
    }
    if (person.pause > 0) {
      person.pause = Math.max(0, person.pause - delta);
      person.walking = false;
      person.currentSpeed += (0 - person.currentSpeed) * Math.min(1, delta * 7);
      person.actionPhase += delta * (1.2 + person.temperament * .8);
      person.blockedByPerson = false;
      person.blockedByRobot = false;
      return;
    }
    const before = pointAt(person.route, person.distance);
    const baseLaneOffset = person.baseLaneOffset ?? 0;
    const laneTarget = person.blockedByPerson ? baseLaneOffset + .38 : baseLaneOffset;
    const proposedLaneOffset = person.laneOffset + (laneTarget - person.laneOffset) * Math.min(1, delta * 3.5);
    const lanePosition = pointWithOffset(before, proposedLaneOffset);
    if (!personHitsSolid(lanePosition.x, lanePosition.z, solids)) person.laneOffset = proposedLaneOffset;
    const segment = person.route.metrics.segments[before.segment];
    const lapStart = Math.floor(person.distance / person.route.metrics.total) * person.route.metrics.total;
    const boundary = lapStart + segment.start + segment.length;
    const probeDistance = Math.min(boundary, person.distance + Math.max(.35, person.speed) * Math.min(.8, delta + .35));
    const probePose = pointAt(person.route, probeDistance);
    const probe = pointWithOffset(probePose, person.laneOffset);
    const clearance = pedestrianClearance(person, probe.x, probe.z, simulation.people, robots);
    person.blockedByPerson = clearance.blockedByPerson;
    person.blockedByRobot = clearance.blockedByRobot;
    const desiredSpeed = person.speed * clearance.factor;
    person.currentSpeed += (desiredSpeed - person.currentSpeed) * Math.min(1, delta * (desiredSpeed > person.currentSpeed ? 2.8 : 6.5));
    if (desiredSpeed === 0 && person.currentSpeed < .08) person.currentSpeed = 0;
    const nextDistance = Math.min(boundary, person.distance + person.currentSpeed * delta);
    const nextPose = pointAt(person.route, nextDistance);
    const next = pointWithOffset(nextPose, person.laneOffset);
    const movementCollision = pedestrianMovementCollision(person, next.x, next.z, simulation.people, robots, solids);
    if (movementCollision) {
      person.currentSpeed = 0;
      person.blockedByObstacle = movementCollision.type === 'solid';
      person.blockedByRobot ||= movementCollision.type === 'robot';
      person.blockedByPerson ||= movementCollision.type === 'person';
      person.walking = false;
      return;
    }
    person.blockedByObstacle = false;
    const dx = next.x - person.position[0];
    const dz = next.z - person.position[2];
    person.walking = Math.hypot(dx, dz) > .001;
    if (person.walking) person.yaw = lerpAngle(person.yaw, Math.atan2(dx, dz), Math.min(1, delta * 7));
    person.position[0] = next.x;
    person.position[2] = next.z;
    person.distance = nextDistance >= boundary ? boundary + .0001 : nextDistance;
    if (nextDistance >= boundary) {
      const arrivedWaypoint = before.segment === person.route.metrics.segments.length - 1 ? 0 : before.segment + 1;
      const arrivedPoint = person.route.points[arrivedWaypoint];
      const canStopHere = !person.stopPoints || person.stopPoints.some(point => Math.hypot(point[0] - arrivedPoint[0], point[1] - arrivedPoint[1]) < .2);
      const dwellRange = person.dwellMax - person.dwellMin;
      person.pause = canStopHere ? person.dwellMin + dwellRange * ((person.id * 0.371 + before.segment * .193) % 1) : 0;
      person.waypoint = arrivedWaypoint;
    }
    if (person.walking) person.walkPhase += delta * person.currentSpeed * (9 + person.stride * 3);
  });
}

function humanInPath(robot, people) {
  const directionX = Math.sin(robot.yaw);
  const directionZ = Math.cos(robot.yaw);
  let nearest = null;
  people.forEach(person => {
    const dx = person.position[0] - robot.position[0];
    const dz = person.position[2] - robot.position[2];
    const distance = Math.hypot(dx, dz);
    if (distance < .001 || distance > 2.8) return;
    const forward = (dx * directionX + dz * directionZ) / distance;
    const lateral = Math.abs(dx * directionZ - dz * directionX);
    if (forward > .35 && lateral < .95 && (!nearest || distance < nearest.distance)) nearest = { person, distance };
  });
  return nearest;
}

function robotHitsSolid(x, z, solids, radius = .58) {
  return solids.some(solid => circleIntersectsSolid(x, z, radius, solid));
}

function distanceToSolidFootprint(x, z, solid) {
  const dx = x - solid.position[0]; const dz = z - solid.position[2]; const yaw = -(solid.yaw || 0);
  const localX = dx * Math.cos(yaw) - dz * Math.sin(yaw);
  const localZ = dx * Math.sin(yaw) + dz * Math.cos(yaw);
  const closestX = Math.max(-solid.scale[0] / 2, Math.min(solid.scale[0] / 2, localX));
  const closestZ = Math.max(-solid.scale[2] / 2, Math.min(solid.scale[2] / 2, localZ));
  return Math.hypot(localX - closestX, localZ - closestZ);
}

function robotMovementCollision(robot, x, z, solids, robots, people = []) {
  const fromX = robot.position[0];
  const fromZ = robot.position[2];
  const length = Math.hypot(x - fromX, z - fromZ);
  const steps = Math.max(1, Math.ceil(length / .18));
  for (let step = 1; step <= steps; step += 1) {
    const amount = step / steps;
    const sampleX = fromX + (x - fromX) * amount;
    const sampleZ = fromZ + (z - fromZ) * amount;
    for (const solid of solids) {
      if (!circleIntersectsSolid(sampleX, sampleZ, robot.radius, solid)) continue;
      const currentHit = circleIntersectsSolid(fromX, fromZ, robot.radius, solid);
      const escaping = currentHit && distanceToSolidFootprint(sampleX, sampleZ, solid) > distanceToSolidFootprint(fromX, fromZ, solid) + .0001;
      if (!escaping) return { type: 'solid', solid };
    }
    for (const other of robots) {
      if (other === robot) continue;
      const currentDistance = Math.hypot(other.position[0] - fromX, other.position[2] - fromZ);
      const sampleDistance = Math.hypot(other.position[0] - sampleX, other.position[2] - sampleZ);
      const minimumDistance = robot.radius + other.radius;
      if (sampleDistance < minimumDistance && !(currentDistance < minimumDistance && sampleDistance > currentDistance)) return { type: 'robot', robot: other };
    }
    for (const person of people) {
      const currentDistance = Math.hypot(person.position[0] - fromX, person.position[2] - fromZ);
      const sampleDistance = Math.hypot(person.position[0] - sampleX, person.position[2] - sampleZ);
      const minimumDistance = robot.radius + .27;
      if (sampleDistance < minimumDistance && !(currentDistance < minimumDistance && sampleDistance > currentDistance)) return { type: 'human', person };
    }
  }
  return null;
}

function chooseAvoidanceSide(robot, person, people, solids) {
  const forwardX = Math.sin(robot.yaw);
  const forwardZ = Math.cos(robot.yaw);
  const rightX = Math.cos(robot.yaw);
  const rightZ = -Math.sin(robot.yaw);
  const options = [-1, 1].map(side => {
    const samples = [.25, .75, 1.35].map(ahead => ({
      x: robot.position[0] + forwardX * ahead + rightX * side * 1.05,
      z: robot.position[2] + forwardZ * ahead + rightZ * side * 1.05
    }));
    if (samples.some(sample => robotHitsSolid(sample.x, sample.z, solids, robot.radius))) return { side, score: -Infinity };
    const { x, z } = samples[1];
    const nearestPerson = people.reduce((nearest, other) => {
      if (other === person) return nearest;
      return Math.min(nearest, Math.hypot(other.position[0] - x, other.position[2] - z));
    }, Infinity);
    const targetClearance = Math.hypot(person.position[0] - x, person.position[2] - z);
    if (nearestPerson < .9 || targetClearance < .82) return { side, score: -Infinity };
    return { side, score: Math.min(nearestPerson, 3) + targetClearance * .2 };
  });
  const best = options.sort((a, b) => b.score - a.score || a.side - b.side)[0];
  return Number.isFinite(best.score) ? best.side : 0;
}

function updateAvoidance(robot, obstruction, people, solids, simulation, delta) {
  if (!robot.avoidingHuman && obstruction && obstruction.distance > 1.18) {
    const side = chooseAvoidanceSide(robot, obstruction.person, people, solids);
    if (side) {
      robot.avoidingHuman = true;
      robot.avoidedPersonId = obstruction.person.id;
      robot.avoidanceTarget = side * 1.05;
      robot.avoidanceTime = 0;
      simulation.detours += 1;
    }
  }
  if (!robot.avoidingHuman) return obstruction;
  robot.avoidanceTime += delta;
  const person = people.find(candidate => candidate.id === robot.avoidedPersonId);
  if (!person) {
    robot.avoidingHuman = false;
  } else {
    const dx = person.position[0] - robot.position[0];
    const dz = person.position[2] - robot.position[2];
    const forward = dx * Math.sin(robot.yaw) + dz * Math.cos(robot.yaw);
    if (forward < -.35 || robot.avoidanceTime > 7) robot.avoidingHuman = false;
  }
  if (!robot.avoidingHuman) {
    robot.avoidedPersonId = null;
    robot.avoidanceTarget = 0;
    return obstruction?.distance < .9 ? obstruction : null;
  }
  if (obstruction && obstruction.person.id !== robot.avoidedPersonId && obstruction.distance < 1.15) return obstruction;
  return null;
}

function robotInPath(robot, robots) {
  const directionX = Math.sin(robot.yaw);
  const directionZ = Math.cos(robot.yaw);
  let nearest = null;
  robots.forEach(other => {
    if (other === robot) return;
    const dx = other.position[0] - robot.position[0];
    const dz = other.position[2] - robot.position[2];
    const distance = Math.hypot(dx, dz);
    if (distance < .001 || distance > 2.4) return;
    const forward = (dx * directionX + dz * directionZ) / distance;
    const lateral = Math.abs(dx * directionZ - dz * directionX);
    const alignment = directionX * Math.sin(other.yaw) + directionZ * Math.cos(other.yaw);
    const otherHasPriority = robotHasPriority(other, robot);
    const shouldYield = alignment > .3 || otherHasPriority;
    if (shouldYield && forward > .3 && lateral < .82 && (!nearest || distance < nearest.distance)) nearest = { robot: other, distance };
  });
  return nearest;
}

function robotHasPriority(robot, other) {
  const robotDirectionX = Math.sin(robot.yaw);
  const robotDirectionZ = Math.cos(robot.yaw);
  const otherDeltaX = other.position[0] - robot.position[0];
  const otherDeltaZ = other.position[2] - robot.position[2];
  const otherForward = otherDeltaX * robotDirectionX + otherDeltaZ * robotDirectionZ;
  const otherLateral = Math.abs(otherDeltaX * robotDirectionZ - otherDeltaZ * robotDirectionX);
  const robotForwardFromOther = (robot.position[0] - other.position[0]) * Math.sin(other.yaw)
    + (robot.position[2] - other.position[2]) * Math.cos(other.yaw);
  const alignment = robotDirectionX * Math.sin(other.yaw) + robotDirectionZ * Math.cos(other.yaw);
  // Роботы с противоположной ориентацией, уже разъезжающиеся друг от друга,
  // не должны запускать взаимный отход только из-за накопленного ожидания.
  if (alignment < -.7 && otherForward < -.15) return false;
  // AMR, физически стоящий впереди в той же полосе, завершает манёвр первым —
  // в том числе когда он уже повернул и уходит с конфликтного участка. Если оба
  // направлены в точку пересечения, ниже срабатывает обычный арбитраж приоритета.
  if (otherForward > .15 && otherLateral < robot.radius + other.radius && robotForwardFromOther <= .15) return false;
  if (alignment > .7) {
    // В попутном потоке ведущего нельзя заставлять сдавать назад к следующему за ним AMR.
    if (Math.abs(otherForward) > .15) return otherForward < 0;
  }
  if (robot.carrying !== other.carrying) return robot.carrying;
  const robotWait = robot.waitingTime + robot.reservationWaitTime;
  const otherWait = other.waitingTime + other.reservationWaitTime;
  if (Math.abs(robotWait - otherWait) > .25) return robotWait > otherWait;
  return robot.id < other.id;
}

function cargoColor(kind) {
  if (kind === 'baggage') return [.48, .16, .12];
  if (kind === 'medical') return [.78, .88, .85];
  return [.72, .50, .25];
}

function taskName(kind) {
  if (kind === 'baggage') return 'Перевозка багажа';
  if (kind === 'medical') return 'Доставка расходников';
  return 'Перемещение паллеты';
}

function makeTask(simulation, route, createdAt = simulation.elapsed) {
  const candidates = route.pickupCandidates || [];
  const pickupIndex = candidates.length ? (route.taskCursor ?? route.initialPickupIndex ?? 0) % candidates.length : -1;
  const pickup = pickupIndex >= 0 ? candidates[pickupIndex] : null;
  if (pickup) route.taskCursor = (pickupIndex + (route.pickupCandidateStride || 1)) % candidates.length;
  const task = {
    id: `RC-${String(simulation.nextTaskId).padStart(4, '0')}`,
    routeId: route.id,
    kind: route.taskProfileKind || route.kind || 'warehouse',
    units: route.unitsPerTrip || 1,
    title: taskName(route.kind),
    status: 'pending',
    createdAt,
    startedAt: null,
    completedAt: null,
    assignedRobotId: null,
    pickupPosition: pickup ? [...pickup.position] : null,
    pickupLabel: pickup?.label || null,
    rackRow: pickup?.rackRow ?? null,
    rackBay: pickup?.bay ?? null
  };
  simulation.nextTaskId += 1;
  return task;
}

function applyTaskRoute(robot, task) {
  if (!task?.pickupPosition) return;
  const chargePoint = robot.route.points[robot.route.chargeWaypoint ?? 0];
  const atCharge = Math.hypot(robot.position[0] - chargePoint[0], robot.position[2] - chargePoint[1]) < 1.6;
  robot.route.points[robot.route.pickupWaypoint ?? 2] = [...task.pickupPosition];
  for (const waypoint of robot.route.pickupAisleWaypoints || []) robot.route.points[waypoint][0] = task.pickupPosition[0];
  robot.route.metrics = routeLengths(robot.route.points);
  if (atCharge) robot.distance = 0;
}

function recordEvent(simulation, type, message) {
  simulation.events.push({ id: simulation.nextEventId, type, message, time: simulation.elapsed });
  simulation.nextEventId += 1;
  if (simulation.events.length > 12) simulation.events.shift();
}

export function triggerSimulationEvent(simulation, type) {
  if (!simulation) return false;
  if (type === 'demand-wave') {
    simulation.robots.forEach(robot => {
      simulation.taskQueue.push(makeTask(simulation, robot.route));
      simulation.taskQueue.push(makeTask(simulation, robot.route));
    });
    simulation.demandWaves += 1;
    recordEvent(simulation, 'demand', `Пиковая волна: +${simulation.robots.length * 2} заданий`);
    return true;
  }
  if (type === 'robot-fault') {
    const candidates = simulation.robots.filter(robot => robot.mode === 'working');
    const robot = candidates.sort((a, b) => b.battery - a.battery || a.id - b.id)[0];
    if (!robot) return false;
    robot.mode = 'fault';
    robot.faultTimer = 12 + (robot.id % 3) * 2;
    robot.currentSpeed = 0;
    robot.blockedByHuman = false;
    robot.blockedByRobot = false;
    robot.reservationBlocked = false;
    simulation.faults += 1;
    recordEvent(simulation, 'fault', `AMR-${String(robot.id).padStart(2, '0')}: остановка для диагностики`);
    return true;
  }
  return false;
}

function assignTask(simulation, robot) {
  if (robot.mode === 'idle') {
    const movingFleet = simulation.robots.filter(candidate => candidate.mode === 'working' || candidate.mode === 'fault').length;
    if (movingFleet >= simulation.trafficCapacity) return false;
    const preferred = simulation.robots
      .filter(candidate => candidate.mode === 'idle' && simulation.taskQueue.some(task => task.routeId === candidate.route.id))
      .sort((a, b) => b.idleTime - a.idleTime || a.id - b.id)[0];
    if (preferred && preferred !== robot) return false;
  }
  const index = simulation.taskQueue.findIndex(task => task.routeId === robot.route.id);
  if (index < 0) return false;
  const [task] = simulation.taskQueue.splice(index, 1);
  task.status = 'active';
  task.startedAt = simulation.elapsed;
  task.assignedRobotId = robot.id;
  robot.activeTask = task;
  applyTaskRoute(robot, task);
  robot.cargoStage = 'waiting';
  robot.carrying = false;
  robot.mode = 'working';
  robot.lastDispatchAt = simulation.elapsed;
  beginRobotOperation(robot, 'dispatch');
  return true;
}

function beginRobotOperation(robot, type) {
  const baseDuration = robot.route.exchangeTimeS ?? (
    robot.robotType === 'forklift' ? 1.8 : robot.robotType === 'medical-cart' ? 1.5 : robot.robotType === 'service-robot' ? .9 : 1.2
  );
  robot.operationType = type;
  robot.operationProgress = 0;
  robot.operationDuration = type === 'dispatch' ? .65 : baseDuration;
  robot.pause = robot.operationDuration;
}

function operationState(robot) {
  if (robot.operationType === 'pickup') {
    if (robot.robotType === 'forklift') return 'ПОДНИМАЕТ ПАЛЛЕТУ';
    if (robot.robotType === 'tow-amr' || robot.robotType === 'baggage-tug') return 'СЦЕПЛЯЕТСЯ С ТЕЛЕЖКОЙ';
    if (robot.robotType === 'medical-cart') return 'ПРИНИМАЕТ РАСХОДНИКИ';
    return 'ЗАБИРАЕТ ГРУЗ';
  }
  if (robot.operationType === 'drop') {
    if (robot.robotType === 'forklift') return 'ОПУСКАЕТ ПАЛЛЕТУ';
    if (robot.robotType === 'medical-cart') return 'ОТКРЫВАЕТ ШКАФ ДЛЯ ПЕРЕДАЧИ';
    return 'ВЫГРУЖАЕТ ГРУЗ';
  }
  return 'ПОЛУЧАЕТ НОВОЕ ЗАДАНИЕ';
}

function completeTask(simulation, robot) {
  if (!robot.activeTask) return;
  const task = robot.activeTask;
  task.status = 'completed';
  task.completedAt = simulation.elapsed;
  task.queueTime = Math.max(0, task.startedAt - task.createdAt);
  task.cycleTime = Math.max(0, task.completedAt - task.startedAt);
  simulation.completedTasks.push(task);
  if (simulation.completedTasks.length > 50) simulation.completedTasks.shift();
  robot.activeTask = null;
  robot.trips += 1;
  simulation.trips += 1;
  simulation.completedUnits += task.units || 1;
}

function average(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

export function getSimulationReport(simulation) {
  const fleetTime = Math.max(.001, simulation.elapsed * Math.max(1, simulation.robots.length));
  const completed = simulation.completedTasks;
  const energyUsed = simulation.robots.reduce((sum, robot) => sum + robot.energyUsed, 0);
  const movingTime = simulation.robots.reduce((sum, robot) => sum + robot.movingTime, 0);
  const chargingTime = simulation.robots.reduce((sum, robot) => sum + robot.chargingTime, 0);
  const idleTime = simulation.robots.reduce((sum, robot) => sum + robot.idleTime, 0);
  return {
    capturedAtSimulationSecond: simulation.elapsed,
    elapsedSeconds: simulation.elapsed,
    fleetSize: simulation.robots.length,
    revisionId: simulation.revisionId,
    zoneId: simulation.zoneId,
    processType: simulation.processType,
    geometryMode: simulation.geometryMode,
    geometry: {
      status: simulation.sceneModified ? 'MODIFIED' : 'BASE',
      baseRevisionId: simulation.baseRevisionId || simulation.revisionId || null,
      economicsStatus: 'UNCHANGED'
    },
    equipmentModelId: simulation.equipmentModelId,
    tasks: {
      active: simulation.robots.filter(robot => robot.activeTask).length,
      queued: simulation.taskQueue.length,
      completed: simulation.trips,
      completedUnits: simulation.completedUnits,
      throughputPerHour: simulation.elapsed > 0 ? simulation.trips * 3600 / simulation.elapsed : 0,
      throughputUnitsPerHour: simulation.elapsed > 0 ? simulation.completedUnits * 3600 / simulation.elapsed : 0,
      requiredUnitsPerHour: simulation.demandPerDay / 24,
      unitsPerTrip: simulation.unitsPerTrip,
      unservedDemandTasks: simulation.unservedDemandTasks,
      averageCycleSeconds: average(completed.map(task => task.cycleTime ?? 0)),
      averageQueueSeconds: average(completed.map(task => task.queueTime ?? 0))
    },
    fleet: {
      utilizationPercent: movingTime / fleetTime * 100,
      availabilityPercent: Math.max(0, 100 - simulation.totalDowntime / fleetTime * 100),
      movingSeconds: movingTime,
      chargingSeconds: chargingTime,
      idleSeconds: idleTime,
      downtimeSeconds: simulation.totalDowntime
    },
    energy: {
      consumedUnits: energyUsed,
      unitsPerCompletedTask: simulation.trips ? energyUsed / simulation.trips : 0
    },
    safety: {
      detours: simulation.detours,
      safetyStops: simulation.safetyStops,
      physicalStops: simulation.physicalStops,
      trafficConflicts: simulation.trafficConflicts,
      humanWaitSeconds: simulation.totalWaitingTime,
      reservationWaitSeconds: simulation.totalReservationWait
    },
    navigation: {
      dynamicReplans: simulation.dynamicReplans,
      activeTrafficLimit: simulation.trafficCapacity,
      robotsUsingDetour: simulation.robots.filter(robot => robot.detourPath?.length).length
    },
    incidents: {
      demandWaves: simulation.demandWaves,
      faults: simulation.faults,
      resolved: simulation.faultsResolved
    },
    robots: simulation.robots.map(robot => ({
      id: robot.id,
      robotType: robot.robotType,
      modelCode: robot.modelCode,
      equipmentModelId: robot.equipmentModelId,
      maxLoadKg: robot.maxLoadKg,
      state: robot.state,
      batteryPercent: robot.battery,
      trips: robot.trips,
      movingSeconds: robot.movingTime,
      chargingSeconds: robot.chargingTime,
      idleSeconds: robot.idleTime,
      downtimeSeconds: robot.downtime,
      waitingSeconds: robot.waitingTime + robot.reservationWaitTime,
      energyUsed: robot.energyUsed,
      lidarReplans: robot.lidarReplans
    }))
  };
}

function generateTaskDemand(simulation) {
  if (!simulation.robots.length || simulation.elapsed < simulation.nextTaskAt) return;
  while (simulation.elapsed >= simulation.nextTaskAt) {
    if (simulation.taskQueue.length < simulation.maxQueueTasks) {
      const route = simulation.robots[simulation.taskCursor % simulation.robots.length].route;
      simulation.taskQueue.push(makeTask(simulation, route, simulation.nextTaskAt));
      simulation.taskCursor += 1;
      simulation.generatedTasks += 1;
    } else simulation.unservedDemandTasks += 1;
    simulation.nextTaskAt += simulation.taskIntervalS;
  }
}

function updateTrafficReservations(simulation) {
  simulation.sharedAisles = simulation.robots.reduce((counts, robot) => {
    const pickup = robot.route.points[robot.route.pickupWaypoint ?? 2];
    if (pickup && robot.route.pickupCandidates) {
      const aisleKey = `aisle:${Math.round(pickup[0] * 10)}`;
      counts.set(aisleKey, (counts.get(aisleKey) || 0) + 1);
    }
    return counts;
  }, new Map());
  const candidates = new Map();
  simulation.robots.forEach(robot => {
    robot.reservationBlocked = false;
    robot.reservationCorridor = false;
    robot.reservedPosition = null;
    if (robot.mode !== 'working' || robot.pause > 0 || !robot.activeTask || robot.detourPath?.length) return;
    const currentPose = pointAt(robot.route, robot.distance);
    const pickup = robot.route.points[robot.route.pickupWaypoint ?? 2];
    const aisleKey = pickup ? `aisle:${Math.round(pickup[0] * 10)}` : null;
    const reserveAisle = aisleKey && (simulation.sharedAisles.get(aisleKey) || 0) > 1 && currentPose.segment <= 4;
    const lookAhead = 1.4 + Math.max(robot.currentSpeed, robot.route.speed * .45) * 1.15;
    const pose = pointAt(robot.route, robot.distance + lookAhead);
    const cellSize = 2.2;
    const key = reserveAisle ? aisleKey : `${Math.round(pose.x / cellSize)}:${Math.round(pose.z / cellSize)}`;
    const group = candidates.get(key) || [];
    group.push({ robot, pose, corridor: reserveAisle });
    candidates.set(key, group);
  });

  const activeKeys = new Set();
  candidates.forEach((group, key) => {
    const corridor = group.some(candidate => candidate.corridor);
    if (group.length < 2 && !corridor) return;
    activeKeys.add(key);
    const existing = simulation.trafficReservations.get(key);
    const hasRobotAhead = candidate => group.some(other => {
      if (other === candidate) return false;
      const dx = other.robot.position[0] - candidate.robot.position[0];
      const dz = other.robot.position[2] - candidate.robot.position[2];
      const distance = Math.hypot(dx, dz);
      if (distance < .001 || distance > 2.5) return false;
      const forward = (dx * Math.sin(candidate.robot.yaw) + dz * Math.cos(candidate.robot.yaw)) / distance;
      const lateral = Math.abs(dx * Math.cos(candidate.robot.yaw) - dz * Math.sin(candidate.robot.yaw));
      return forward > .25 && lateral < .88;
    });
    const existingCandidate = existing && existing.expiresAt > simulation.elapsed
      ? group.find(candidate => candidate.robot.id === existing.ownerId && !hasRobotAhead(candidate))
      : null;
    const owner = existingCandidate || [...group].sort((a, b) => {
      if (hasRobotAhead(a) !== hasRobotAhead(b)) return hasRobotAhead(a) ? 1 : -1;
      if (a.robot.carrying !== b.robot.carrying) return a.robot.carrying ? -1 : 1;
      if (a.robot.reservationWaitTime !== b.robot.reservationWaitTime) return b.robot.reservationWaitTime - a.robot.reservationWaitTime;
      return a.robot.id - b.robot.id;
    })[0];
    simulation.trafficReservations.set(key, { ownerId: owner.robot.id, expiresAt: simulation.elapsed + 1.15 });
    group.forEach(candidate => {
      candidate.robot.reservedPosition = [candidate.pose.x, candidate.pose.z];
      candidate.robot.reservationBlocked = candidate.robot.id !== owner.robot.id;
      candidate.robot.reservationCorridor = corridor;
    });
  });
  simulation.trafficReservations.forEach((reservation, key) => {
    if (!activeKeys.has(key) || reservation.expiresAt <= simulation.elapsed) simulation.trafficReservations.delete(key);
  });
  simulation.activeReservations = simulation.trafficReservations.size;
}

function tryPlanRobotDetour(robot, simulation, solids) {
  if (simulation.elapsed - robot.lastReplanAt < 1.4 || robot.pause > 0 || robot.operationType) return false;
  const before = pointAt(robot.route, robot.distance);
  const segment = robot.route.metrics.segments[before.segment];
  const lapStart = Math.floor(robot.distance / robot.route.metrics.total) * robot.route.metrics.total;
  const boundary = lapStart + segment.start + segment.length;
  if (boundary - robot.distance < 1.5) return false;
  const targetDistance = Math.min(boundary - .08, robot.distance + 5.2);
  const target = pointAt(robot.route, targetDistance);
  const dynamic = simulation.robots.filter(other => other !== robot && other.mode !== 'charging');
  const navigationBounds = {
    minX: Math.max(simulation.navigationBounds.minX, Math.min(robot.position[0], target.x) - 4.8),
    maxX: Math.min(simulation.navigationBounds.maxX, Math.max(robot.position[0], target.x) + 4.8),
    minZ: Math.max(simulation.navigationBounds.minZ, Math.min(robot.position[2], target.z) - 4.8),
    maxZ: Math.min(simulation.navigationBounds.maxZ, Math.max(robot.position[2], target.z) + 4.8)
  };
  const path = planGridPath([robot.position[0], robot.position[2]], [target.x, target.z], {
    solids,
    dynamic,
    radius: robot.radius,
    step: .68,
    bounds: navigationBounds,
    maxIterations: 1200
  });
  robot.lastReplanAt = simulation.elapsed;
  if (!path?.length) return false;
  robot.detourPath = path;
  robot.detourTargetDistance = targetDistance;
  robot.blockedDuration = 0;
  robot.reservationBlocked = false;
  robot.reservedPosition = null;
  robot.lidarReplans += 1;
  simulation.dynamicReplans += 1;
  recordEvent(simulation, 'navigation', `AMR-${String(robot.id).padStart(2, '0')}: лидар построил объезд`);
  return true;
}

function advanceRobotDetour(robot, simulation, delta, solids) {
  if (!robot.detourPath?.length) return false;
  const target = robot.detourPath[0];
  const dx = target[0] - robot.position[0]; const dz = target[1] - robot.position[2];
  const distance = Math.hypot(dx, dz);
  if (distance < .13) {
    const completionCollision = robotMovementCollision(robot, target[0], target[1], solids, simulation.robots, simulation.people);
    if (completionCollision) {
      robot.currentSpeed = 0;
      robot.blockedByRobot = completionCollision.type === 'robot';
      robot.blockedByHuman = completionCollision.type === 'human';
      robot.blockedBySolid = completionCollision.type === 'solid';
      if (completionCollision.robot && robotHasPriority(robot, completionCollision.robot)) {
        completionCollision.robot.forcedYieldBy = robot.id;
        completionCollision.robot.forcedYieldTime = 0;
      }
      robot.blockedDuration += delta;
      if (robot.blockedDuration > 1.45 && simulation.elapsed - robot.lastReplanAt >= 1.4) {
        const previousPath = robot.detourPath;
        robot.detourPath = null;
        if (!tryPlanRobotDetour(robot, simulation, solids)) robot.detourPath = previousPath;
      }
      robot.state = 'ЛИДАР · ОЖИДАЕТ СВОБОДНУЮ ТОЧКУ';
      return true;
    }
    robot.detourPath.shift();
    if (!robot.detourPath.length) {
      robot.distance = robot.detourTargetDistance;
      const pose = pointAt(robot.route, robot.distance);
      robot.position = [pose.x, .42, pose.z];
      robot.yaw = pose.yaw;
      robot.detourTargetDistance = null;
      robot.currentSpeed = 0;
      robot.state = 'ВОЗВРАЩАЕТСЯ НА ОСНОВНОЙ МАРШРУТ';
    }
    return true;
  }
  const desiredSpeed = Math.min(robot.route.speed * .78, Math.max(.3, distance * 1.6));
  robot.currentSpeed += (desiredSpeed - robot.currentSpeed) * Math.min(1, delta * 3.4);
  const travel = Math.min(distance, Math.max(0, robot.currentSpeed) * delta);
  const nextX = robot.position[0] + dx / distance * travel;
  const nextZ = robot.position[2] + dz / distance * travel;
  const collision = robotMovementCollision(robot, nextX, nextZ, solids, simulation.robots, simulation.people);
  if (collision) {
    robot.currentSpeed = 0;
    robot.blockedByRobot = collision.type === 'robot';
    robot.blockedByHuman = collision.type === 'human';
    robot.blockedBySolid = collision.type === 'solid';
    if (collision.robot && robotHasPriority(robot, collision.robot)) {
      collision.robot.forcedYieldBy = robot.id;
      collision.robot.forcedYieldTime = 0;
    }
    robot.blockedDuration += delta;
    if (robot.blockedDuration > 1.45 && simulation.elapsed - robot.lastReplanAt >= 1.4) {
      const previousPath = robot.detourPath;
      robot.detourPath = null;
      if (!tryPlanRobotDetour(robot, simulation, solids)) robot.detourPath = previousPath;
    }
    robot.state = 'ЛИДАР · ПЕРЕСТРОЕНИЕ ОБЪЕЗДА';
    return true;
  }
  robot.blockedByRobot = false; robot.blockedByHuman = false; robot.blockedBySolid = false;
  robot.position = [nextX, .42, nextZ];
  robot.yaw = lerpAngle(robot.yaw, Math.atan2(dx, dz), Math.min(1, delta * 6));
  robot.movingTime += delta; robot.workingTime += delta;
  const energy = travel * robot.energyPerMeter;
  robot.energyUsed += energy; robot.battery = Math.max(5, robot.battery - energy);
  if (robot.battery <= robot.chargeThreshold) robot.needsCharge = true;
  robot.state = `ЛИДАР · ДИНАМИЧЕСКИЙ ОБЪЕЗД ${robot.detourPath.length}`;
  return true;
}

function advanceForcedYield(robot, simulation, delta, solids) {
  if (!robot.forcedYieldBy) return false;
  const priorityRobot = simulation.robots.find(other => other.id === robot.forcedYieldBy);
  robot.forcedYieldTime += delta;
  if (!priorityRobot || Math.hypot(priorityRobot.position[0] - robot.position[0], priorityRobot.position[2] - robot.position[2]) > 2.35 || robot.forcedYieldTime > 4) {
    robot.forcedYieldBy = null; robot.forcedYieldTime = 0; return false;
  }
  const reverseDistance = Math.max(0, robot.distance - .48 * delta);
  const pose = pointAt(robot.route, reverseDistance);
  const position = pointWithOffset(pose, robot.avoidanceOffset);
  const collision = robotMovementCollision(robot, position.x, position.z, solids, simulation.robots, simulation.people);
  if (!collision) {
    robot.distance = reverseDistance;
    robot.position = [position.x, .42, position.z];
    robot.yaw = pose.yaw;
    robot.currentSpeed = -.48;
    robot.backingUp = true;
  } else {
    robot.currentSpeed = 0;
    if (collision.robot && collision.robot !== priorityRobot) {
      // Если отход перекрыт третьим AMR, освобождать цепочку должен инициатор
      // приоритета. Иначе он бесконечно требует физически невозможный манёвр.
      priorityRobot.forcedYieldBy = robot.id;
      priorityRobot.forcedYieldTime = 0;
      robot.forcedYieldBy = null;
      robot.forcedYieldTime = 0;
    }
  }
  robot.state = 'ЛИДАР · ОСВОБОЖДАЕТ ПРИОРИТЕТНЫЙ ПРОЕЗД';
  return true;
}

export function createSimulation(scene) {
  const routes = scene.routes.map(route => ({
    ...route,
    points: route.points.map(point => [...point]),
    pickupCandidates: route.pickupCandidates?.map(candidate => ({ ...candidate, position: [...candidate.position] })),
    taskCursor: route.initialPickupIndex ?? 0,
    metrics: routeLengths(route.points)
  }));
  const robots = routes.map(route => {
    const initialPose = pointAt(route, route.metrics.total * route.phase);
    const pickup = route.pickupWaypoint ?? 2;
    const drop = route.dropWaypoint ?? 4;
    return ({
    id: route.id,
    entityType: 'robot',
    route,
    distance: route.metrics.total * route.phase,
    trips: 0,
    position: [initialPose.x, .42, initialPose.z],
    yaw: initialPose.yaw,
    state: 'ВЫПОЛНЯЕТ ЗАДАНИЕ',
    carrying: initialPose.segment >= pickup && initialPose.segment < drop,
    cargoStage: initialPose.segment >= pickup && initialPose.segment < drop ? 'carried' : 'waiting',
    battery: 46 + (route.id * 13) % 47,
    mode: 'working',
    needsCharge: false,
    chargeThreshold: 30,
    chargeRate: 11,
    energyUsed: 0,
    kind: route.kind || 'warehouse',
    label: route.label || 'Складской AMR',
    process: route.process || 'Паллетные перемещения',
    color: route.color || [.08, .55, .42],
    robotType: route.robotType || 'pallet-amr',
    modelCode: route.modelCode || 'RC-P1200',
    equipmentModelId: route.equipmentModelId || route.modelCode || 'RC-P1200',
    radius: route.radius || .61,
    maxLoadKg: route.maxLoadKg || 1200,
    drive: route.drive || 'electric',
    cargoLabel: route.cargoLabel || 'Груз',
    energyPerMeter: route.energyPerMeter || .12,
    currentSpeed: route.speed,
    pause: 0,
    blockedByHuman: false,
    blockedByRobot: false,
    blockedBySolid: false,
    physicalStopActive: false,
    avoidingHuman: false,
    backingUp: false,
    avoidedPersonId: null,
    avoidanceOffset: 0,
    avoidanceTarget: 0,
    avoidanceTime: 0,
    waitingTime: 0,
    safetyStopActive: false,
    reservationBlocked: false,
    reservationCorridor: false,
    reservationWaitTime: 0,
    reservationStopActive: false,
    reservedPosition: null,
    blockedDuration: 0,
    solidBlockedDuration: 0,
    detourPath: null,
    detourTargetDistance: null,
    lastReplanAt: -10,
    lidarReplans: 0,
    forcedYieldBy: null,
    forcedYieldTime: 0,
    faultTimer: 0,
    downtime: 0,
    movingTime: 0,
    workingTime: 0,
    chargingTime: 0,
    idleTime: 0,
    operationType: null,
    operationProgress: 0,
    operationDuration: 0
  });
  });
  robots.forEach((robot, index) => {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const overlapsSolid = robotHitsSolid(robot.position[0], robot.position[2], scene.solids, robot.radius);
      const overlapsRobot = robots.slice(0, index).some(other => Math.hypot(other.position[0] - robot.position[0], other.position[2] - robot.position[2]) < robot.radius + other.radius);
      if (!overlapsSolid && !overlapsRobot) break;
      robot.distance += .65;
      const pose = pointAt(robot.route, robot.distance);
      robot.position = [pose.x, .42, pose.z];
      robot.yaw = pose.yaw;
      const pickup = robot.route.pickupWaypoint ?? 2;
      const drop = robot.route.dropWaypoint ?? 4;
      robot.carrying = pose.segment >= pickup && pose.segment < drop;
    }
  });
  const people = (scene.people || []).map(person => {
    const route = { points: person.points, metrics: routeLengths(person.points) };
    const distance = route.metrics.total * person.phase;
    const pose = pointAt(route, distance);
    return {
      ...person,
      entityType: 'person',
      route,
      distance,
      position: [pose.x, 0, pose.z],
      yaw: pose.yaw,
      walkPhase: person.phase * 3,
      actionPhase: person.phase * 5,
      pause: 0,
      waypoint: pose.segment,
      walking: true,
      currentSpeed: 0,
      blockedByPerson: false,
      blockedByRobot: false,
      blockedByObstacle: false,
      baseLaneOffset: person.baseLaneOffset ?? person.laneOffset ?? 0,
      laneOffset: person.laneOffset ?? 0
    };
  });
  people.forEach((person, index) => {
    if (person.allowInsideSolid) return;
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const overlapsSolid = personHitsSolid(person.position[0], person.position[2], scene.solids);
      const overlapsPerson = people.slice(0, index).some(other => Math.hypot(other.position[0] - person.position[0], other.position[2] - person.position[2]) < .5);
      const overlapsRobot = robots.some(robot => Math.hypot(robot.position[0] - person.position[0], robot.position[2] - person.position[2]) < robot.radius + .27);
      if (!overlapsSolid && !overlapsPerson && !overlapsRobot) break;
      person.distance += .35;
      const pose = pointAt(person.route, person.distance);
      const position = pointWithOffset(pose, person.laneOffset);
      person.position = [position.x, 0, position.z];
      person.yaw = pose.yaw;
    }
  });
  const simulation = {
    robots, people, deliveredCargo: [], elapsed: 0, trips: 0, completedUnits: 0, speedMultiplier: 1,
    taskQueue: [], completedTasks: [], nextTaskId: 1,
    taskIntervalS: scene.scenario?.taskIntervalS || 7.5,
    nextTaskAt: scene.scenario?.taskIntervalS || 7.5,
    taskCursor: 0, generatedTasks: 0, unservedDemandTasks: 0,
    maxQueueTasks: Math.max(2, robots.length * 2),
    revisionId: scene.scenario?.revisionId || null,
    zoneId: scene.scenario?.zoneId || null,
    processType: scene.scenario?.processType || null,
    geometryMode: scene.scenario?.geometryMode || null,
    equipmentModelId: scene.scenario?.equipmentModelId || null,
    demandPerDay: scene.scenario?.demandPerDay || 0,
    unitsPerTrip: scene.scenario?.unitsPerTrip || 1,
    detours: 0, safetyStops: 0, totalWaitingTime: 0,
    trafficReservations: new Map(), activeReservations: 0, trafficConflicts: 0, totalReservationWait: 0,
    events: [], nextEventId: 1, demandWaves: 0, faults: 0, faultsResolved: 0, totalDowntime: 0,
    physicalStops: 0,
    dynamicReplans: 0,
    navigationBounds: { minX: -scene.config.width / 2 + .7, maxX: scene.config.width / 2 - .7, minZ: -scene.config.depth / 2 + .7, maxZ: scene.config.depth / 2 - .7 },
    sharedAisles: robots.reduce((counts, robot) => {
      const pickup = robot.route.points[robot.route.pickupWaypoint ?? 2];
      if (pickup && robot.route.pickupCandidates) {
        const aisleKey = `aisle:${Math.round(pickup[0] * 10)}`;
        counts.set(aisleKey, (counts.get(aisleKey) || 0) + 1);
      }
      return counts;
    }, new Map()),
    trafficCapacity: Math.min(robots.length, scene.config.template === 'warehouse' ? 2 : 3)
  };
  if (scene.scenario && robots.length && !scene.routes[0]?.stationaryCycle) {
    // Start one real task immediately so low-frequency demand does not look like
    // a frozen visualization while preserving the calculated long-run cadence.
    simulation.taskQueue.push(makeTask(simulation, robots[0].route, 0));
    simulation.generatedTasks = 1;
  }
  robots.forEach((robot, index) => {
    robot.distance = 0;
    const charge = pointAt(robot.route, 0);
    robot.position = [charge.x, .42, charge.z];
    robot.yaw = charge.yaw;
    robot.carrying = false;
    robot.cargoStage = 'waiting';
    if (!scene.scenario && index < simulation.trafficCapacity) {
      robot.activeTask = makeTask(simulation, robot.route, 0);
      robot.activeTask.status = 'active';
      robot.activeTask.startedAt = 0;
      robot.activeTask.assignedRobotId = robot.id;
      robot.lastDispatchAt = 0;
    } else {
      robot.activeTask = null;
      robot.mode = 'idle';
    }
    if (!scene.scenario) simulation.taskQueue.push(makeTask(simulation, robot.route, 0));
  });
  recordEvent(simulation, 'system', 'Сценарий запущен, диспетчер активен');
  return simulation;
}

export function updateSimulation(simulation, delta, solids = []) {
  const simDelta = delta * simulation.speedMultiplier;
  simulation.elapsed += simDelta;
  updatePeople(simulation, simDelta, solids, simulation.robots);
  generateTaskDemand(simulation);
  updateTrafficReservations(simulation);
  simulation.robots.forEach(robot => {
    if (robot.mode === 'fault') {
      robot.currentSpeed = 0;
      robot.blockedByHuman = false;
      robot.blockedByRobot = false;
      robot.reservationBlocked = false;
      robot.avoidingHuman = false;
      robot.avoidanceTarget = 0;
      robot.faultTimer = Math.max(0, robot.faultTimer - simDelta);
      robot.downtime += simDelta;
      simulation.totalDowntime += simDelta;
      robot.state = `ДИАГНОСТИКА · ${Math.ceil(robot.faultTimer)} СЕК.`;
      if (robot.faultTimer <= 0) {
        robot.mode = 'working';
        simulation.faultsResolved += 1;
        recordEvent(simulation, 'recovery', `AMR-${String(robot.id).padStart(2, '0')}: возвращён в работу`);
        robot.state = 'ДИАГНОСТИКА ЗАВЕРШЕНА';
      }
      return;
    }
    if (robot.mode === 'idle') {
      robot.blockedByHuman = false;
      robot.blockedByRobot = false;
      robot.currentSpeed = 0;
      robot.reservationBlocked = false;
      if (!assignTask(simulation, robot)) {
        robot.idleTime += simDelta;
        robot.avoidanceTarget = 0;
        robot.avoidanceOffset += (robot.avoidanceTarget - robot.avoidanceOffset) * Math.min(1, simDelta * 3.2);
        robot.state = 'ОЖИДАЕТ ЗАДАНИЕ';
        return;
      }
    }
    if (robot.route.stationaryCycle) {
      robot.currentSpeed = 0;
      robot.workingTime += simDelta;
      robot.operationType = 'palletizing';
      robot.operationDuration = robot.route.cycleDurationS;
      robot.operationProgress = ((robot.operationProgress || 0) + simDelta / robot.operationDuration) % 1;
      robot.state = 'УКЛАДЫВАЕТ КОРОБА НА ПАЛЛЕТУ';
      if (robot.activeTask && robot.operationProgress < simDelta / robot.operationDuration) {
        completeTask(simulation, robot);
        robot.mode = 'idle';
        robot.operationType = null;
        recordEvent(simulation, 'drop', `Ячейка-${String(robot.id).padStart(2, '0')}: паллета завершена`);
      }
      return;
    }
    if (robot.mode === 'charging') {
      robot.chargingTime += simDelta;
      robot.blockedByHuman = false;
      robot.blockedByRobot = false;
      robot.avoidingHuman = false;
      robot.avoidanceTarget = 0;
      robot.avoidanceOffset += (robot.avoidanceTarget - robot.avoidanceOffset) * Math.min(1, simDelta * 3.2);
      robot.currentSpeed = 0;
      robot.reservationBlocked = false;
      robot.pause = 0;
      robot.battery = Math.min(100, robot.battery + robot.chargeRate * simDelta);
      if (robot.battery >= 99.5) {
        robot.battery = 100;
        robot.needsCharge = false;
        if (!robot.activeTask && !assignTask(simulation, robot)) robot.mode = 'idle';
        else robot.mode = 'working';
      }
      const chargingPose = pointAt(robot.route, robot.distance);
      robot.position = [chargingPose.x, .42, chargingPose.z];
      robot.yaw = chargingPose.yaw;
      robot.state = robot.mode === 'charging' ? 'ЗАРЯЖАЕТСЯ' : 'ЗАРЯДКА ЗАВЕРШЕНА';
      return;
    }
    if (advanceForcedYield(robot, simulation, simDelta, solids)) return;
    if (advanceRobotDetour(robot, simulation, simDelta, solids)) return;
    const detectedHuman = humanInPath(robot, simulation.people);
    const obstruction = updateAvoidance(robot, detectedHuman, simulation.people, solids, simulation, simDelta);
    const traffic = robotInPath(robot, simulation.robots);
    robot.backingUp = false;
    robot.blockedByHuman = Boolean(obstruction);
    robot.blockedByRobot = Boolean(traffic);
    robot.blockedBySolid = false;
    robot.blockedDuration = traffic || (robot.reservationBlocked && !robot.reservationCorridor)
      ? robot.blockedDuration + simDelta
      : Math.max(0, robot.blockedDuration - simDelta * 1.8);
    if (robot.blockedDuration > .85 && tryPlanRobotDetour(robot, simulation, solids)) {
      advanceRobotDetour(robot, simulation, simDelta, solids);
      return;
    }
    const blockingDistance = Math.min(obstruction?.distance ?? Infinity, traffic?.distance ?? Infinity);
    if (robot.pause > 0) {
      robot.pause = Math.max(0, robot.pause - simDelta);
      robot.currentSpeed = 0;
      if (robot.operationType) {
        robot.operationProgress = Math.min(1, robot.operationProgress + simDelta / Math.max(.01, robot.operationDuration));
        if (robot.pause <= 0) robot.operationType = null;
      }
    } else {
      const before = pointAt(robot.route, robot.distance);
      const segment = robot.route.metrics.segments[before.segment];
      const lapStart = Math.floor(robot.distance / robot.route.metrics.total) * robot.route.metrics.total;
      const boundary = lapStart + segment.start + segment.length;
      const remaining = Math.max(0, boundary - robot.distance);
      let targetSpeed = remaining < 1.4 ? Math.max(.28, robot.route.speed * remaining / 1.4) : robot.route.speed;
      if (robot.avoidingHuman) targetSpeed *= .62;
      if (robot.reservationBlocked) targetSpeed = 0;
      if (Number.isFinite(blockingDistance)) targetSpeed *= Math.max(0, Math.min(1, (blockingDistance - .75) / 1.35));
      robot.currentSpeed += (targetSpeed - robot.currentSpeed) * Math.min(1, simDelta * 2.8);
      if (blockingDistance < .92) robot.currentSpeed = 0;
      if (robot.reservationBlocked) robot.currentSpeed = 0;
      const previousDistance = robot.distance;
      const nextDistance = robot.distance + robot.currentSpeed * simDelta;
      const candidateDistance = nextDistance >= boundary ? boundary + .0001 : nextDistance;
      const candidatePose = pointAt(robot.route, candidateDistance);
      const candidatePosition = pointWithOffset(candidatePose, robot.avoidanceOffset);
      let physicalCollision = robotMovementCollision(robot, candidatePosition.x, candidatePosition.z, solids, simulation.robots, simulation.people);
      if (physicalCollision?.type === 'robot' && traffic?.robot === physicalCollision.robot && traffic.distance < 1.75) {
        const reverseDistance = Math.max(0, robot.distance - .42 * simDelta);
        const reversePose = pointAt(robot.route, reverseDistance);
        const reversePosition = pointWithOffset(reversePose, robot.avoidanceOffset);
        const reverseCollision = robotMovementCollision(robot, reversePosition.x, reversePosition.z, solids, simulation.robots, simulation.people);
        if (!reverseCollision) {
          robot.distance = reverseDistance;
          robot.currentSpeed = -.42;
          robot.backingUp = true;
          physicalCollision = null;
        }
      }
      if (physicalCollision) {
        robot.currentSpeed = 0;
        if (physicalCollision.type === 'solid') {
          robot.blockedBySolid = true;
          robot.solidBlockedDuration += simDelta;
          if (robot.solidBlockedDuration > .65) tryPlanRobotDetour(robot, simulation, solids);
        }
        else if (physicalCollision.type === 'human') robot.blockedByHuman = true;
        else {
          robot.blockedByRobot = true;
          if (physicalCollision.robot && robotHasPriority(robot, physicalCollision.robot)) {
            physicalCollision.robot.forcedYieldBy = robot.id;
            physicalCollision.robot.forcedYieldTime = 0;
          }
        }
        if (!robot.physicalStopActive) simulation.physicalStops += 1;
        robot.physicalStopActive = true;
      } else if (robot.backingUp) {
        // Короткий контролируемый отход освобождает узкий конфликтный участок.
      } else if (nextDistance >= boundary) {
        robot.distance = boundary + .0001;
        robot.pause = .45 + (robot.id % 3) * .18;
        robot.currentSpeed = 0;
        const arrivedWaypoint = before.segment === robot.route.metrics.segments.length - 1 ? 0 : before.segment + 1;
        if (arrivedWaypoint === (robot.route.pickupWaypoint ?? 2) && robot.activeTask) {
          robot.carrying = true;
          robot.cargoStage = 'carried';
          beginRobotOperation(robot, 'pickup');
        }
        if (arrivedWaypoint === (robot.route.dropWaypoint ?? 4) && robot.carrying && robot.activeTask) {
          beginRobotOperation(robot, 'drop');
          robot.carrying = false;
          robot.cargoStage = 'delivered';
          const base = robot.route.dropPosition || robot.route.points[arrivedWaypoint];
          const sameKind = simulation.deliveredCargo.filter(item => item.kind === robot.kind).length;
          simulation.deliveredCargo.push({
            kind: robot.kind,
            color: cargoColor(robot.kind),
            position: [base[0] + (sameKind % 4) * .72, .34 + Math.floor((sameKind % 12) / 4) * .56, base[1] + Math.floor(sameKind / 12) * .85]
          });
          if (simulation.deliveredCargo.length > 36) simulation.deliveredCargo.shift();
          completeTask(simulation, robot);
        }
        if (arrivedWaypoint === (robot.route.chargeWaypoint ?? 0) && robot.needsCharge && !robot.carrying) {
          robot.mode = 'charging';
          robot.pause = 0;
        } else if (arrivedWaypoint === (robot.route.chargeWaypoint ?? 0) && !robot.activeTask) {
          robot.mode = 'idle';
        }
      } else robot.distance = nextDistance;
      if (!physicalCollision) { robot.physicalStopActive = false; robot.solidBlockedDuration = 0; }
      const travelled = Math.max(0, robot.distance - previousDistance);
      const energy = travelled * robot.energyPerMeter;
      robot.energyUsed += energy;
      robot.battery = Math.max(5, robot.battery - energy);
      if (robot.battery <= robot.chargeThreshold) robot.needsCharge = true;
    }
    const pose = pointAt(robot.route, robot.distance);
    robot.workingTime += simDelta;
    if (robot.currentSpeed > .06) robot.movingTime += simDelta;
    const proposedOffset = robot.avoidanceOffset + (robot.avoidanceTarget - robot.avoidanceOffset) * Math.min(1, simDelta * 2.8);
    const proposedPosition = pointWithOffset(pose, proposedOffset);
    const lateralCollision = robotMovementCollision(robot, proposedPosition.x, proposedPosition.z, solids, simulation.robots, simulation.people);
    if (!lateralCollision) robot.avoidanceOffset = proposedOffset;
    else {
      robot.avoidingHuman = false;
      robot.avoidanceTarget = 0;
      if (lateralCollision.type === 'solid') robot.blockedBySolid = true;
      else if (lateralCollision.type === 'human') robot.blockedByHuman = true;
      else robot.blockedByRobot = true;
    }
    const position = pointWithOffset(pose, robot.avoidanceOffset);
    robot.position = [position.x, .42, position.z];
    robot.yaw = pose.yaw;
    const safetyStopped = (robot.blockedByHuman || robot.blockedByRobot || robot.blockedBySolid) && robot.currentSpeed < .06;
    if (safetyStopped) {
      robot.waitingTime += simDelta;
      simulation.totalWaitingTime += simDelta;
      if (!robot.safetyStopActive) simulation.safetyStops += 1;
    }
    robot.safetyStopActive = safetyStopped;
    if (robot.reservationBlocked) {
      robot.reservationWaitTime += simDelta;
      simulation.totalReservationWait += simDelta;
      if (!robot.reservationStopActive) simulation.trafficConflicts += 1;
    }
    robot.reservationStopActive = robot.reservationBlocked;
    if (robot.mode === 'charging') robot.state = 'ЗАРЯЖАЕТСЯ';
    else if (robot.blockedBySolid) robot.state = 'ОСТАНОВКА · ПРЕПЯТСТВИЕ НА МАРШРУТЕ';
    else if (robot.blockedByHuman) robot.state = 'УСТУПАЕТ ДОРОГУ ЧЕЛОВЕКУ';
    else if (robot.reservationBlocked) robot.state = 'ОЖИДАЕТ РАЗРЕШЕНИЕ ДИСПЕТЧЕРА';
    else if (robot.backingUp) robot.state = 'ОСВОБОЖДАЕТ ПРОЕЗД';
    else if (robot.blockedByRobot) robot.state = 'ОЖИДАЕТ СВОБОДНЫЙ МАРШРУТ';
    else if (robot.avoidingHuman) robot.state = 'БЕЗОПАСНО ОБЪЕЗЖАЕТ ЧЕЛОВЕКА';
    else if (robot.pause > 0 && robot.operationType) robot.state = operationState(robot);
    else if (robot.pause > 0) robot.state = robot.kind === 'medical' ? 'ПЕРЕДАЁТ РАСХОДНИКИ' : robot.kind === 'baggage' ? 'ПРИНИМАЕТ БАГАЖ' : 'ПОГРУЗКА / РАЗГРУЗКА';
    else if (robot.needsCharge && !robot.carrying) robot.state = 'ВОЗВРАЩАЕТСЯ НА ЗАРЯДКУ';
    else if (!robot.activeTask) robot.state = 'ВОЗВРАЩАЕТСЯ В ЗОНУ ОЖИДАНИЯ';
    else if (pose.segment === 0) robot.state = 'ВЫЕЗЖАЕТ С ЗАРЯДКИ';
    else if (robot.carrying) robot.state = robot.kind === 'medical' ? 'ДОСТАВЛЯЕТ РАСХОДНИКИ' : robot.kind === 'baggage' ? 'ДОСТАВЛЯЕТ БАГАЖ' : 'ДОСТАВЛЯЕТ ПАЛЛЕТУ';
    else if (pose.segment === 5) robot.state = 'ВОЗВРАЩАЕТСЯ';
    else robot.state = 'ВЫПОЛНЯЕТ ЗАДАНИЕ';
  });
}
