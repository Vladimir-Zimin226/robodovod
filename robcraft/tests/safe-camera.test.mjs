import test from 'node:test';
import assert from 'node:assert/strict';
import { Player } from '../src/player.js';
import { createSafePlan, safeRoute } from '../src/integration/safe-playback-v2.js';
import { updateFacilityCamera } from '../src/integration/facility-renderer.js';
import { playbackCase } from './support/safe-case.js';

test('safe scene keeps walls solid during manual flight', () => {
  const previous = globalThis.document;
  const canvas = { addEventListener() {} };
  globalThis.document = { addEventListener() {}, pointerLockElement: canvas };
  try {
    const player = new Player(canvas);
    player.enabled = true;
    player.flying = true;
    player.position = [0, 5, 0];
    player.keys.add('KeyW');
    const wall = { position: [0, 1.6, -.8], scale: [4, 3.2, .4] };
    player.update(.1, [wall], true);
    assert.equal(player.position[2], 0);
    player.update(.1, [wall], false);
    assert.ok(player.position[2] < 0, 'legacy free flight is unchanged');
  } finally {
    globalThis.document = previous;
  }
});

test('warehouse camera follows a robot steadily after a brief opening view', () => {
  const plan = createSafePlan(playbackCase('warehouse', 15).spec);
  const robots = plan.robots.map(robot => ({ ...robot, ...safeRoute(plan, robot.ordinal).home,
    stage: 'OUTBOUND', stageLabel: 'В зону отгрузки', areaLabel: `Стеллаж ${robot.ordinal + 1}` }));
  const frame = { plan, robots }, camera = { position: [0, 20, 20] };
  updateFacilityCamera(camera, frame, 0);
  assert.equal(camera.currentShot.id, 'facility-overview');
  updateFacilityCamera(camera, frame, 3);
  const first = camera.currentShot.id;
  assert.match(first, /^facility-robot-/);
  for (const second of [8, 15, 22]) {
    updateFacilityCamera(camera, frame, second);
    assert.equal(camera.currentShot.id, first);
  }
  updateFacilityCamera(camera, frame, 27);
  assert.equal(camera.currentShot.id, 'facility-overview');
  updateFacilityCamera(camera, frame, 29);
  assert.equal(camera.currentShot.id, 'facility-overview');
  updateFacilityCamera(camera, frame, 32);
  assert.match(camera.currentShot.id, /^facility-robot-/);
  assert.notEqual(camera.currentShot.id, first);
});

test('warehouse follow camera settles close enough to read the robot and its load', () => {
  const plan = createSafePlan(playbackCase('warehouse', 15).spec);
  const robot = { ...plan.robots[0], ...safeRoute(plan, 0).home,
    stage: 'OUTBOUND', stageLabel: 'В зону отгрузки', areaLabel: 'Стеллаж 1' };
  const frame = { plan, robots: [robot] }, camera = { position: [0, 20, 20] };
  for (let step = 0; step <= 70; step += 1) updateFacilityCamera(camera, frame, step / 10);
  assert.match(camera.currentShot.id, /^facility-robot-/);
  const x = robot.x - plan.width / 2, z = robot.y - plan.height / 2;
  assert.ok(Math.hypot(camera.position[0] - x, camera.position[2] - z) < 9);
  assert.ok(camera.position[1] < 7);
});

test('a robot selected in the plan remains the 3D camera subject', () => {
  const plan = createSafePlan(playbackCase('warehouse', 15).spec);
  const robots = plan.robots.map(robot => ({ ...robot, ...safeRoute(plan, robot.ordinal).home,
    stage: 'OUTBOUND', stageLabel: 'В зону отгрузки', areaLabel: `Стеллаж ${robot.ordinal + 1}` }));
  const camera = { position: [0, 20, 20], facilityPinnedOrdinal: 3 };
  for (const second of [0, 3, 11, 25, 32]) updateFacilityCamera(camera, { plan, robots }, second);
  assert.equal(camera.currentShot.id, `facility-robot-${robots[3].id}`);
  assert.equal(camera.facilityFollowOrdinal, 3);
});
