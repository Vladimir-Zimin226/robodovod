import { createFacilityPlayback, facilityFrameAt } from './facility-playback.js';
import { facilityWorldPoint } from '../world/facility.js';

export function applyFacilityPlayback(simulation, scene, report, elapsedSeconds) {
  if (!simulation.facilityPlayback || simulation.facilityPlaybackReport !== report) {
    simulation.facilityPlayback = createFacilityPlayback(scene.facilityPlan, scene.scenarioSpec, report);
    simulation.facilityPlaybackReport = report;
  }
  const frame = facilityFrameAt(simulation.facilityPlayback, elapsedSeconds);
  simulation.facilityFrame = frame;
  simulation.elapsed = elapsedSeconds;
  simulation.trips = frame.completedJobs;
  simulation.taskQueue = [];
  simulation.generatedTasks = simulation.facilityPlayback.jobs.filter(job => job.release <= simulation.facilityPlayback.calendar.workAt(elapsedSeconds)).length;
  simulation.completedUnits = 0;
  frame.robots.forEach((pose, index) => {
    const robot = simulation.robots[index];
    if (!robot) return;
    const [x, z] = facilityWorldPoint(pose);
    robot.position = [x, .42, z]; robot.yaw = pose.yaw;
    robot.state = `${pose.stageLabel} · ${pose.areaLabel}`;
    robot.mode = ['WAITING', 'OFF_SHIFT', 'ALLOWANCE', 'WAIT_RESOURCE'].includes(pose.stage) ? 'idle' : 'working';
    robot.activeTask = pose.jobSequence === null ? null : { id: pose.jobSequence, units: pose.units };
    robot.carrying = pose.carrying; robot.cargoStage = pose.carrying ? 'carried' : 'delivered';
    robot.operationType = pose.stage === 'LOAD' ? 'pickup' : pose.stage === 'UNLOAD' ? 'drop' : null;
    robot.operationProgress = pose.progress;
    robot.facilityPose = pose;
    robot.currentSpeed = ['OUTBOUND', 'RETURN', 'WORK'].includes(pose.stage) ? 1 : 0;
    robot.route.points = [...pose.route.outbound, ...pose.route.work, ...pose.route.returning].map(facilityWorldPoint);
    robot.route.pickupWaypoint = 0;
    robot.route.dropPosition = facilityWorldPoint(pose.route.handoff);
    robot.trips = pose.completedJobs;
    simulation.completedUnits += simulation.facilityPlayback.byRobot[index].slice(0, pose.completedJobs).reduce((sum, job) => sum + job.units, 0);
  });
  // No synthetic battery, faults, energy or collision observations are added.
  return frame;
}

export function updateFacilityCamera(camera, frame, elapsedWallSeconds) {
  const active = frame.robots.filter(robot => !['WAITING', 'OFF_SHIFT', 'ALLOWANCE', 'WAIT_RESOURCE'].includes(robot.stage));
  const robot = (active.length ? active : frame.robots)[Math.floor(elapsedWallSeconds / 12) % Math.max(1, (active.length ? active : frame.robots).length)];
  const overview = !robot || elapsedWallSeconds % 12 >= 9;
  const [x,z] = robot ? facilityWorldPoint(robot) : [0,0];
  camera.position = overview ? [0, 35, 25] : [x + 6, 8, z + 7];
  const target = overview ? [0, 0, 0] : [x, .8, z];
  const dx = target[0] - camera.position[0], dy = target[1] - camera.position[1], dz = target[2] - camera.position[2];
  camera.yaw = Math.atan2(dx, -dz);
  camera.pitch = Math.atan2(dy, Math.hypot(dx,dz));
  camera.currentShot = { id: overview ? 'facility-overview' : `facility-robot-${robot.id}`,
    caption: overview ? 'Общий план · маршруты внутри объекта' : `Робот ${robot.ordinal + 1} · ${robot.stageLabel} · ${robot.areaLabel}` };
}
