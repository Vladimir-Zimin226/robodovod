import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { CameraDirector, cameraPointBlocked, cameraViewClear } from '../src/camera-director.js';
import { createSimulation, triggerSimulationEvent, updateSimulation } from '../src/simulation.js';
import { generateWorld, generateWorldFromScenarioSpec } from '../src/world/generator.js';

const fixtureUrl = new URL('../../contracts/fixtures/scenario-spec-v1.golden.json', import.meta.url);
const golden = JSON.parse(readFileSync(fixtureUrl, 'utf8'));

function scenario(quantity, revisionDigit) {
  const spec = structuredClone(golden);
  spec.revision_id = `calc_${String(revisionDigit).padStart(16, '0')}`;
  spec.fleet[0].quantity = quantity;
  return spec;
}

function advance(scene, simulation, director, seconds, delta = .1) {
  const cameraBlockers = [...scene.solids, ...scene.staticObjects.filter(item => item.type === 'roof')];
  let previous = [...director.position];
  let previousYaw = director.yaw;
  let previousPitch = director.pitch;
  let maximumStep = 0;
  for (let elapsed = 0; elapsed < seconds; elapsed += delta) {
    updateSimulation(simulation, delta, scene.solids);
    director.update(delta, scene, simulation);
    const travelled = Math.hypot(...director.position.map((value, index) => value - previous[index]));
    maximumStep = Math.max(maximumStep, travelled);
    assert.equal(cameraPointBlocked(director.position, cameraBlockers), false, `камера вошла в solid на ${elapsed} с`);
    assert.ok(Math.abs(Math.atan2(Math.sin(director.yaw - previousYaw), Math.cos(director.yaw - previousYaw))) <= director.angularSpeed * delta + 1e-8);
    assert.ok(Math.abs(director.pitch - previousPitch) <= director.angularSpeed * delta + 1e-8);
    previous = [...director.position];
    previousYaw = director.yaw;
    previousPitch = director.pitch;
  }
  return maximumStep;
}

test('AUTOPILOT бесконечно ротирует планы без телепортов и зацикливания', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'DIRECTOR-LONG', robotCount: 6 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const director = new CameraDirector({ maxSpeed: 5 });
  director.reset(scene, simulation);
  const maximumStep = advance(scene, simulation, director, 420);

  assert.equal(director.active, true);
  assert.equal(director.mode, 'AUTOPILOT');
  assert.ok(director.history.length >= 30, `смен планов: ${director.history.length}`);
  assert.ok(new Set(director.history.map(item => item.id.replace(/-\d+$/, ''))).size >= 4);
  assert.ok(new Set(director.history.filter(item => /^(follow|operation|charging)-/.test(item.id)).map(item => item.id.split('-').at(-1))).size >= 2);
  assert.ok(maximumStep <= .500001, `скачок камеры ${maximumStep} м`);
  for (let index = 1; index < director.history.length; index += 1) {
    assert.notEqual(director.history[index].id, director.history[index - 1].id);
  }
  assert.ok(cameraViewClear(director.position, director.currentShot.target, [...scene.solids, ...scene.staticObjects.filter(item => item.type === 'roof')]));
});

test('AUTOPILOT сразу начинает следящий план и камера заметно движется', () => {
  const scene = generateWorldFromScenarioSpec(scenario(2, 41));
  const simulation = createSimulation(scene);
  simulation.people = [];
  const director = new CameraDirector();
  director.reset(scene, simulation);
  const start = [...director.position];

  const maximumStep = advance(scene, simulation, director, 3);
  const distance = Math.hypot(...director.position.map((value, index) => value - start[index]));

  assert.ok(director.currentShot);
  assert.ok(maximumStep > .01);
  assert.ok(distance > 1, `камера прошла только ${distance} м`);
  assert.ok(simulation.robots.some(robot => Math.abs(robot.currentSpeed) > .05));
});

test('событие временно получает приоритет и камера затем продолжает программу', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'DIRECTOR-EVENT', robotCount: 3 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const director = new CameraDirector();
  director.reset(scene, simulation);
  advance(scene, simulation, director, 2);
  assert.equal(triggerSimulationEvent(simulation, 'robot-fault'), true);
  director.update(.1, scene, simulation);

  assert.match(director.currentShot.id, /^event-fault-/);
  assert.match(director.caption, /AMR-/);
  const eventHistoryLength = director.history.length;
  advance(scene, simulation, director, 12);
  assert.ok(director.history.length > eventHistoryLength);
  assert.equal(director.currentShot.event, undefined);
});

test('смена revision_id не сбрасывает камеру и автопоказ', () => {
  const firstScene = generateWorldFromScenarioSpec(scenario(3, 31));
  const firstSimulation = createSimulation(firstScene);
  firstSimulation.people = [];
  const director = new CameraDirector({ maxSpeed: 4 });
  director.reset(firstScene, firstSimulation);
  advance(firstScene, firstSimulation, director, 20);
  const before = [...director.position];

  const nextScene = generateWorldFromScenarioSpec(scenario(5, 32));
  const nextSimulation = createSimulation(nextScene);
  nextSimulation.people = [];
  director.update(.1, nextScene, nextSimulation);
  const revisionStep = Math.hypot(...director.position.map((value, index) => value - before[index]));

  assert.equal(director.revisionId, nextScene.scenario.revisionId);
  assert.equal(director.revisionTransitions, 1);
  assert.equal(director.active, true);
  assert.ok(revisionStep <= .400001);
  advance(nextScene, nextSimulation, director, 30);
  assert.ok(director.history.some(item => item.revisionId === nextScene.scenario.revisionId));
});

test('пауза и возврат режиссёра сохраняют текущую симуляцию и позицию', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'DIRECTOR-RESUME', robotCount: 2 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const director = new CameraDirector();
  director.reset(scene, simulation);
  advance(scene, simulation, director, 15);
  const elapsed = simulation.elapsed;
  director.suspend();
  const manual = { position: [...director.position], yaw: director.yaw, pitch: director.pitch };
  director.update(5, scene, simulation);
  assert.deepEqual(director.position, manual.position);

  director.resume(scene, simulation, manual);
  director.update(.1, scene, simulation);
  assert.equal(simulation.elapsed, elapsed);
  assert.equal(director.mode, 'AUTOPILOT');
  assert.equal(director.active, true);
});
