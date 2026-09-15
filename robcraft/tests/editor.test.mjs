import test from 'node:test';
import assert from 'node:assert/strict';
import { generateWorld } from '../src/world/generator.js';
import { createSimulation, getSimulationReport, updateSimulation } from '../src/simulation.js';
import { SceneEditorModel } from '../src/editor/editor.js';
import { circleIntersectsSolid } from '../src/editor/collisions.js';
import { applyScenePatch, assertScenePatchCompatible, createScenePatch, exportSceneDocument, importSceneDocument, SCENE_PATCH_VERSION, scenarioVisualFingerprint, scenePatchHasChanges, scenePatchSummary } from '../src/editor/scene-patch.js';

function editor(seed = 'EDITOR-MVP') {
  return new SceneEditorModel(generateWorld({ template: 'warehouse', seed, robotCount: 3 }));
}

test('базовая сцена остаётся воспроизводимой после введения ScenePatch', () => {
  const config = { template: 'warehouse', seed: 'PATCH-BASE', width: 48, depth: 38, rackRows: 5, robotCount: 4, occupancy: 72 };
  const a = applyScenePatch(generateWorld(config), createScenePatch(config));
  const b = applyScenePatch(generateWorld(config), createScenePatch(config));
  assert.deepEqual(a.staticObjects, b.staticObjects);
  assert.deepEqual(a.solids, b.solids);
});

test('ScenePatch применяется поверх базы, не меняя базовую конфигурацию', () => {
  const base = generateWorld({ seed: 'PATCH-APPLY' });
  const model = new SceneEditorModel(base);
  const wall = model.entities().find(item => item.kind === 'wall');
  assert.equal(model.move(wall.id, [100, 0, 0], { grid: false }), true);
  assert.notDeepEqual(model.entity(wall.id).position, wall.position);
  assert.equal(base.staticObjects.find(item => item.editorId === wall.id).position[0], wall.parts[0].position[0]);
  assert.equal(model.history.present.format, SCENE_PATCH_VERSION);
});

test('создание, перемещение, поворот, масштабирование и удаление работают как реальные операции', () => {
  const model = editor('CRUD');
  const id = model.create('decor', [90, .5, 90]);
  assert.ok(id);
  assert.equal(model.move(id, [1, 0, 2], { grid: false }), true);
  assert.equal(model.rotate(id), true);
  assert.equal(model.resize(id, 1, 0, { grid: false }), true);
  const object = model.entity(id);
  assert.deepEqual(object.position, [91, .5, 92]);
  assert.equal(object.yaw, Math.PI / 2);
  assert.equal(object.scale[0], 2);
  assert.ok(model.scene.solids.some(solid => solid.editorId === id));
  assert.equal(model.delete(id), true);
  assert.equal(model.entity(id), null);
  assert.equal(model.scene.solids.some(solid => solid.editorId === id), false);
});

test('дублирование создаёт одну отменяемую операцию', () => {
  const model = editor('DUPLICATE');
  const id = model.create('decor', [80, .5, 80]);
  const copy = model.duplicate(id, [2, 0, 0]);
  assert.ok(copy);
  assert.ok(model.entity(copy));
  model.undo();
  assert.equal(model.entity(copy), null);
  assert.ok(model.entity(id));
});

test('Undo/Redo хранит не менее двадцати действий', () => {
  const model = editor('HISTORY');
  const id = model.create('decor', [100, .5, 100]);
  for (let i = 0; i < 20; i += 1) assert.equal(model.move(id, [1, 0, 0], { grid: false }), true);
  const finalX = model.entity(id).position[0];
  model.undo(); model.undo();
  assert.equal(model.entity(id).position[0], finalX - 2);
  model.redo(); model.redo();
  assert.equal(model.entity(id).position[0], finalX);
});

test('экспорт и импорт восстанавливают отдельно seed и пользовательский патч', () => {
  const model = editor('ROUNDTRIP');
  model.create('fence', [75, .6, 75]);
  const text = exportSceneDocument(model.history.present);
  const imported = importSceneDocument(text);
  assert.equal(imported.baseConfig.seed, 'ROUNDTRIP');
  assert.deepEqual(imported.patch, model.history.present);
  const restored = applyScenePatch(generateWorld(imported.baseConfig), imported.patch);
  assert.deepEqual(restored.staticObjects, model.scene.staticObjects);
});

test('коллизии обновляются и учитывают поворот', () => {
  const model = editor('COLLISION-UPDATE');
  const id = model.create('wall', [90, 1.5, 90]);
  const before = model.scene.solids.find(solid => solid.editorId === id);
  assert.equal(circleIntersectsSolid(91.7, 90, .2, before), true);
  model.rotate(id);
  const after = model.scene.solids.find(solid => solid.editorId === id);
  assert.equal(circleIntersectsSolid(91.7, 90, .2, after), false);
  assert.equal(circleIntersectsSolid(90, 91.7, .2, after), true);
  assert.equal(model.create('decor', [90, .5, 90]), null);
});

test('модель робота заменяется только совместимым типом', () => {
  const model = editor('ROBOT-MODEL');
  assert.equal(model.editRobot(1, { robotType: 'forklift' }), true);
  assert.equal(model.scene.routes[0].robotType, 'forklift');
  assert.equal(model.editRobot(1, { robotType: 'medical-cart' }), false);
  model.undo();
  assert.notEqual(model.scene.routes[0].robotType, 'forklift');
});

test('старт, зарядка и маршрутная точка робота сохраняются в патче', () => {
  const model = editor('ROBOT-ROUTE');
  const route = model.scene.routes[0];
  const points = structuredClone(route.points);
  points.splice(2, 0, [77, 78]);
  model.editRobot(route.id, { startPosition: [70, 71], chargePosition: [72, 73], points });
  assert.deepEqual(model.scene.routes[0].points[0], [70, 71]);
  assert.deepEqual(model.scene.routes[0].points[1], [72, 73]);
  assert.ok(model.scene.routes[0].points.some(point => point[0] === 77));
});

test('сброс возвращает исходную сгенерированную сцену', () => {
  const model = editor('RESET');
  const original = model.scene.staticObjects;
  model.create('decor', [90, .5, 90]);
  model.reset();
  assert.deepEqual(model.scene.staticObjects, original);
  assert.deepEqual(model.history.present.created, []);
});

test('расчётный ScenePatch привязан к revision_id и визуальному fingerprint', () => {
  const config = { template: 'warehouse', seed: 'BOUND-PATCH' };
  const spec = { template: 'warehouse', seed: 'BOUND-PATCH', facility: { width_m: 48 }, zones: [], fleet: [], task_profiles: [] };
  const fingerprint = scenarioVisualFingerprint(spec);
  const patch = createScenePatch(config, { revisionId: 'calc_0123456789abcdef', visualFingerprint: fingerprint });
  assert.equal(assertScenePatchCompatible(patch, { revisionId: 'calc_0123456789abcdef', visualFingerprint: fingerprint }), patch);
  assert.throws(() => assertScenePatchCompatible(patch, { revisionId: 'calc_ffffffffffffffff', visualFingerprint: fingerprint }), /другой ревизии/);
  assert.throws(() => assertScenePatchCompatible(patch, { revisionId: 'calc_0123456789abcdef', visualFingerprint: 'visual_00000000' }), /визуальной базе/);
});

test('расчётный ScenePatch нельзя применить к другой зоне той же ревизии', () => {
  const binding = { revisionId: 'calc_0123456789abcdef', visualFingerprint: 'visual_1234abcd', zoneId: 'receiving' };
  const patch = createScenePatch({ template: 'warehouse', seed: 'ZONE-PATCH' }, binding);
  assertScenePatchCompatible(patch, binding);
  assert.throws(() => assertScenePatchCompatible(patch, { ...binding, zoneId: 'shipping' }), /другой зоне/);
});

test('сводка ScenePatch и сброс сохраняют расчётную привязку', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'BOUND-RESET' });
  const binding = { revisionId: 'calc_0123456789abcdef', visualFingerprint: 'visual_1234abcd' };
  const model = new SceneEditorModel(base, createScenePatch(base.config, binding));
  model.create('decor', [90, .5, 90]);
  assert.equal(scenePatchHasChanges(model.history.present), true);
  assert.deepEqual(scenePatchSummary(model.history.present), { objects: 0, created: 1, deleted: 0, robots: 0 });
  model.reset();
  assert.equal(scenePatchHasChanges(model.history.present), false);
  assert.equal(model.history.present.base.revision_id, binding.revisionId);
  assert.equal(model.history.present.base.visual_fingerprint, binding.visualFingerprint);
});

test('импорт отклоняет неизвестные поля ScenePatch', () => {
  const patch = createScenePatch({ template: 'warehouse', seed: 'STRICT' });
  const document = JSON.parse(exportSceneDocument(patch));
  document.scenePatch.surprise = true;
  assert.throws(() => importSceneDocument(document), /неизвестные поля/);
});

test('операционный отчёт явно маркирует изменённую геометрию без пересчёта экономики', () => {
  const simulation = createSimulation(generateWorld({ seed: 'REPORT-PATCH' }));
  simulation.sceneModified = true;
  simulation.baseRevisionId = 'calc_0123456789abcdef';
  assert.deepEqual(getSimulationReport(simulation).geometry, {
    status: 'MODIFIED', baseRevisionId: 'calc_0123456789abcdef', economicsStatus: 'UNCHANGED'
  });
});

test('изменённая геометрия останавливает робота и старый сценарий продолжает работать', () => {
  const base = generateWorld({ seed: 'ROUTE-BLOCK', robotCount: 1 });
  const model = new SceneEditorModel(base);
  const simulation = createSimulation(model.scene);
  const robot = simulation.robots[0];
  const obstaclePosition = [robot.position[0] + Math.sin(robot.yaw) * .9, .5, robot.position[2] + Math.cos(robot.yaw) * .9];
  assert.ok(model.create('decor', obstaclePosition));
  updateSimulation(simulation, .5, model.scene.solids);
  assert.equal(robot.blockedBySolid, true);
  assert.equal(robot.currentSpeed, 0);
});
