import test from 'node:test';
import assert from 'node:assert/strict';
import { planGridPath } from '../src/navigation.js';
import { generateWorld } from '../src/world/generator.js';
import { createSimulation, updateSimulation } from '../src/simulation.js';

test('A* строит свободный путь вокруг статического препятствия', () => {
  const wall = { position: [0, 1, 0], scale: [1, 2, 4], yaw: 0 };
  const path = planGridPath([-4, 0], [4, 0], {
    solids: [wall], radius: .55, step: .5,
    bounds: { minX: -5, maxX: 5, minZ: -4, maxZ: 4 }
  });
  assert.ok(path?.length > 1);
  assert.ok(path.some(point => Math.abs(point[1]) > 2.4));
});

test('два робота при шести рядах получают удалённые точки разных стеллажей', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'RACK-DISTRIBUTION', rackRows: 6, robotCount: 2 });
  const pickups = scene.routes.map(route => route.pickupCandidates[route.initialPickupIndex]);
  assert.notEqual(pickups[0].rackRow, pickups[1].rackRow);
  assert.ok(Math.abs(pickups[0].rackRow - pickups[1].rackRow) >= 4);
  assert.ok(scene.routes.every(route => new Set(route.pickupCandidates.map(candidate => candidate.rackRow)).size === 6));
});

test('следующие задания ротируются между ячейками и рядами', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'TASK-PICKUPS', rackRows: 6, robotCount: 2 });
  const simulation = createSimulation(scene);
  simulation.robots.forEach(robot => {
    const queued = simulation.taskQueue.find(task => task.routeId === robot.route.id);
    assert.ok(queued.pickupPosition);
    assert.notDeepEqual(queued.pickupPosition, robot.activeTask.pickupPosition);
  });
});

test('плотный парк не образует неразрешимый поезд в транспортной зоне', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'DENSE-LIDAR', rackRows: 6, robotCount: 8, occupancy: 80 });
  const simulation = createSimulation(scene);
  for (let step = 0; step < 5000; step += 1) updateSimulation(simulation, .05, scene.solids);
  assert.ok(simulation.trips >= 2);
  assert.ok(Math.max(...simulation.robots.map(robot => robot.waitingTime)) < 5);
  assert.equal(simulation.trafficCapacity, 2);
  assert.ok(simulation.robots.filter(robot => robot.mode === 'working').length <= simulation.trafficCapacity);
  assert.equal(simulation.robots.some(robot => robot.blockedByRobot), false);
});

test('лидар перестраивает маршрут вокруг внезапного твёрдого препятствия', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'LIDAR-OBSTACLE', rackRows: 5, robotCount: 1 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const robot = simulation.robots[0];
  const lane = robot.route.metrics.segments[2];
  const laneStart = robot.route.points[2];
  const laneEnd = robot.route.points[3];
  const amount = 3 / lane.length;
  robot.distance = lane.start + 3;
  robot.position = [laneStart[0] + (laneEnd[0] - laneStart[0]) * amount, .42, laneStart[1] + (laneEnd[1] - laneStart[1]) * amount];
  robot.yaw = Math.atan2(laneEnd[0] - laneStart[0], laneEnd[1] - laneStart[1]);
  robot.pause = 0;
  const obstacle = {
    position: [robot.position[0] + Math.sin(robot.yaw) * 1.05, .5, robot.position[2] + Math.cos(robot.yaw) * 1.05],
    scale: [.5, 1, .5]
  };
  const start = [...robot.position];
  const solids = [...scene.solids, obstacle];
  for (let step = 0; step < 500; step += 1) updateSimulation(simulation, .05, solids);
  assert.ok(robot.lidarReplans > 0, JSON.stringify({ state: robot.state, start, position: robot.position, obstacle, distance: robot.distance, solidBlockedDuration: robot.solidBlockedDuration }));
  assert.ok(Math.hypot(robot.position[0] - start[0], robot.position[2] - start[2]) > 1.5);
  assert.equal(robot.blockedBySolid, false);
});
