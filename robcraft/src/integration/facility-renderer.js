import { createFacilityPlayback, facilityFrameAt } from './facility-playback.js';
import { facilityWorldPoint } from '../world/facility.js';
import { createSafePlayback, safeFrameAt, sweptHitsRectangle } from './safe-playback-v2.js';
import { safeWorldPoint } from '../world/safe-facility-v2.js';

export function applyFacilityPlayback(simulation, scene, report, elapsedSeconds) {
  if (!simulation.facilityPlayback || simulation.facilityPlaybackReport !== report) {
    simulation.facilityPlayback = scene.safePlaybackPlan ? createSafePlayback(scene.safePlaybackPlan, scene.scenarioSpec, report)
      : createFacilityPlayback(scene.facilityPlan, scene.scenarioSpec, report);
    simulation.facilityPlaybackReport = report;
  }
  const frame = scene.safePlaybackPlan ? safeFrameAt(simulation.facilityPlayback, elapsedSeconds) : facilityFrameAt(simulation.facilityPlayback, elapsedSeconds);
  const worldPoint = scene.safePlaybackPlan ? (pose) => safeWorldPoint(scene.safePlaybackPlan, pose) : facilityWorldPoint;
  if (scene.safePlaybackPlan) frame.plan = scene.safePlaybackPlan;
  simulation.facilityFrame = frame;
  simulation.elapsed = elapsedSeconds;
  simulation.trips = frame.completedJobs;
  simulation.taskQueue = [];
  const jobs = simulation.facilityPlayback.jobs, work = simulation.facilityPlayback.calendar.workAt(elapsedSeconds);
  let low = 0, high = jobs.length;
  while (low < high) { const middle = (low + high) >>> 1; if (jobs[middle].release <= work) low = middle + 1; else high = middle; }
  simulation.generatedTasks = low;
  simulation.completedUnits = 0;
  frame.robots.forEach((pose, index) => {
    const robot = simulation.robots[index];
    if (!robot) return;
    const [x, z] = worldPoint(pose);
    robot.position = [x, .42, z]; robot.yaw = pose.yaw;
    if (scene.safePlaybackPlan) { robot.visualFootprint = scene.safePlaybackPlan.footprint; robot.radius = robot.visualFootprint.radius; }
    robot.state = `${pose.stageLabel} · ${pose.areaLabel}`;
    robot.mode = ['WAITING', 'OFF_SHIFT', 'ALLOWANCE', 'WAIT_RESOURCE'].includes(pose.stage) ? 'idle' : 'working';
    robot.activeTask = pose.jobSequence === null ? null : { id: pose.jobSequence, units: pose.units };
    robot.carrying = pose.carrying; robot.cargoStage = pose.carrying ? 'carried' : 'delivered';
    robot.operationType = pose.stage === 'LOAD' ? 'pickup' : pose.stage === 'UNLOAD' ? 'drop' : null;
    robot.operationProgress = pose.progress;
    robot.facilityPose = pose;
    robot.currentSpeed = ['OUTBOUND', 'RETURN', 'WORK'].includes(pose.stage) ? 1 : 0;
    robot.route.points = [...(pose.route.toLoad || []), ...pose.route.outbound, ...pose.route.work, ...pose.route.returning].map(worldPoint);
    robot.route.pickupWaypoint = 0;
    robot.route.dropPosition = worldPoint(pose.route.handoff);
    robot.trips = pose.completedJobs;
    if (!scene.safePlaybackPlan) simulation.completedUnits += simulation.facilityPlayback.byRobot[index].slice(0, pose.completedJobs).reduce((sum, job) => sum + job.units, 0);
  });
  if (scene.safePlaybackPlan) simulation.completedUnits = frame.completedUnits;
  // No synthetic battery, faults, energy or collision observations are added.
  return frame;
}

export function updateFacilityCamera(camera, frame, elapsedWallSeconds) {
  camera.facilityStartedAt ??= elapsedWallSeconds;
  const active = frame.robots.filter(robot => !['WAITING', 'OFF_SHIFT', 'ALLOWANCE', 'WAIT_RESOURCE'].includes(robot.stage));
  const robot = (active.length ? active : frame.robots)[Math.floor(elapsedWallSeconds / 12) % Math.max(1, (active.length ? active : frame.robots).length)];
  const overview = !robot || (frame.plan ? (elapsedWallSeconds - camera.facilityStartedAt) % 12 < 4 : elapsedWallSeconds % 12 >= 9);
  const [x,z] = robot ? frame.plan ? safeWorldPoint(frame.plan, robot) : facilityWorldPoint(robot) : [0,0];
  const plan = frame.plan;
  const clamp = (value, limit) => Math.max(-limit / 2 + 1.3, Math.min(limit / 2 - 1.3, value));
  const candidates = [[-7, 8], [7, 8], [-7, -8], [7, -8]];
  const freeSide = !plan ? candidates[1] : candidates.map(([dx, dz]) => {
    const point = { x: clamp(x + dx, plan.width) + plan.width / 2, y: clamp(z + dz, plan.height) + plan.height / 2 };
    const target = { x: x + plan.width / 2, y: z + plan.height / 2 };
    const crossings = [...plan.walls, ...plan.furniture, ...(plan.environment || [])]
      .filter(rect => !rect.overhead && sweptHitsRectangle(point, target, rect, .15)).length;
    return { offset: [dx, dz], score: crossings * 100 + Math.hypot(point.x - target.x, point.y - target.y) * -.01 };
  }).sort((a, b) => a.score - b.score)[0].offset;
  const desired = overview ? [0, Math.max(35, (plan?.height || 32) * .92), Math.max(25, (plan?.height || 32) * .68)]
    : [plan ? clamp(x + freeSide[0], plan.width) : x + freeSide[0], 9,
      plan ? clamp(z + freeSide[1], plan.height) : z + freeSide[1]];
  const target = overview ? [0, 0, 0] : [x, .8, z];
  const delta = Math.max(0, Math.min(.1, elapsedWallSeconds - (camera.facilityLastTime ?? elapsedWallSeconds)));
  const mix = camera.facilityLastTime === undefined ? 1 : 1 - Math.exp(-delta * 2.8);
  camera.position = camera.position.map((value, index) => value + (desired[index] - value) * mix);
  camera.facilityLastTime = elapsedWallSeconds;
  const dx = target[0] - camera.position[0], dy = target[1] - camera.position[1], dz = target[2] - camera.position[2];
  camera.yaw = Math.atan2(dx, -dz);
  camera.pitch = Math.atan2(dy, Math.hypot(dx,dz));
  camera.currentShot = { id: overview ? 'facility-overview' : `facility-robot-${robot.id}`,
    caption: overview ? 'Общий план · маршруты внутри объекта' : `Робот ${robot.ordinal + 1} · ${robot.stageLabel} · ${robot.areaLabel}` };
}
