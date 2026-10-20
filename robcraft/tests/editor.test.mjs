import test from 'node:test';
import assert from 'node:assert/strict';
import { generateWorld } from '../src/world/generator.js';
import { createSimulation, getSimulationReport, preserveOperationalRobotPositions, updateSimulation } from '../src/simulation.js';
import { SceneEditorModel } from '../src/editor/editor.js';
import { circleIntersectsSolid, solidsOverlap } from '../src/editor/collisions.js';
import { triangulateRoom } from '../src/editor/room-polygon.js';
import { operationalAnchors, planOperationalPath } from '../src/editor/operational.js';
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

test('стены по двум точкам и дверной проём сохраняются одной операцией Undo', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'WALL-DOOR', width: 48, depth: 38 });
  base.staticObjects = [];
  base.solids = [];
  base.routes = [];
  const model = new SceneEditorModel(base);
  const ids = model.createWallSegment([-6, 0], [6, 0], { door: true });
  assert.equal(ids.length, 3);
  assert.equal(model.history.present.created.filter(item => item.type === 'wall').length, 2);
  assert.equal(model.history.present.created.find(item => item.kind === 'door_frame').solid, false);
  assert.equal(model.scene.solids.length, 2);
  assert.equal(model.scene.solids.some(solid => circleIntersectsSolid(0, 0, .34, solid)), false);
  assert.equal(model.scene.solids.some(solid => circleIntersectsSolid(3, 0, .34, solid)), true);
  const restored = importSceneDocument(exportSceneDocument(model.history.present));
  assert.equal(new SceneEditorModel(base, restored.patch).scene.staticObjects.filter(item => item.type === 'wall').length, 2);
  model.undo();
  assert.equal(model.scene.solids.length, 0);
  model.redo();
  assert.equal(model.scene.solids.length, 2);
  assert.ok(model.create('decor', [8, .5, 0]));
  assert.equal(model.createWallSegment([7, 0], [9, 0]), null);
});

test('комната полигоном создаёт замкнутые стены и пол, удаляется одним действием', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'ROOM-POLYGON', width: 48, depth: 38 });
  base.staticObjects = []; base.solids = []; base.routes = [];
  const model = new SceneEditorModel(base);
  const points = [[-8, -6], [4, -6], [4, -2], [0, -2], [0, 5], [-8, 5]];
  assert.equal(triangulateRoom(points).length, points.length - 2);
  const id = model.addRoom('Участок сборки', points);
  assert.ok(id);
  assert.equal(model.scene.editorRooms.length, 1);
  assert.equal(model.scene.solids.length, points.length);
  assert.equal(model.move(model.history.present.rooms[0].wall_ids[0], [1, 0, 0]), false);
  const restored = importSceneDocument(exportSceneDocument(model.history.present));
  assert.deepEqual(new SceneEditorModel(base, restored.patch).scene.editorRooms[0].points, points);
  model.undo();
  assert.equal(model.scene.editorRooms.length, 0);
  assert.equal(model.scene.solids.length, 0);
  model.redo();
  assert.equal(model.scene.solids.length, points.length);
  assert.equal(model.delete(model.history.present.rooms[0].wall_ids[0]), true);
  assert.equal(model.scene.editorRooms.length, 0);
  assert.equal(model.scene.solids.length, 0);
  model.undo();
  assert.equal(model.scene.editorRooms.length, 1);
  assert.equal(model.addRoom('Пересечение', [[-3, -3], [3, 3], [-3, 3], [3, -3]]), null);
});

test('проём комнаты открывается и закрывается атомарно, связанные части удаляются вместе', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'ROOM-DOOR', width: 48, depth: 38 });
  base.staticObjects = []; base.solids = []; base.routes = [];
  const model = new SceneEditorModel(base);
  const points = [[-8, -6], [4, -6], [4, 5], [-8, 5]];
  const roomId = model.addRoom('Проходная', points);
  assert.ok(roomId);
  assert.equal(model.toggleRoomDoor(roomId, 0), true);
  const room = model.scene.editorRooms[0];
  assert.equal(room.doors.length, 1);
  assert.equal(model.scene.solids.length, 5);
  assert.equal(model.scene.solids.some(solid => circleIntersectsSolid(-2, -6, .34, solid)), false);
  assert.equal(model.scene.solids.some(solid => circleIntersectsSolid(-6, -6, .34, solid)), true);
  const frameId = room.doors[0].frame_id;
  assert.equal(model.scene.staticObjects.find(item => item.id === frameId).solid, false);
  const restored = importSceneDocument(exportSceneDocument(model.history.present));
  assert.equal(new SceneEditorModel(base, restored.patch).scene.editorRooms[0].doors[0].frame_id, frameId);
  model.undo();
  assert.equal(model.scene.editorRooms[0].doors, undefined);
  assert.equal(model.scene.solids.length, 4);
  model.redo();
  assert.equal(model.scene.editorRooms[0].doors.length, 1);
  assert.equal(model.toggleRoomDoor(roomId, 0), true);
  assert.equal(model.scene.editorRooms[0].doors.length, 0);
  assert.equal(model.scene.solids.length, 4);
  model.undo();
  assert.equal(model.delete(frameId), true);
  assert.equal(model.scene.editorRooms.length, 0);
  assert.equal(model.scene.solids.length, 0);
});

test('операционные точки CHARGE/WORK/DROPOFF строят проверяемый путь и реагируют на стену', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'OPERATIONAL-PATH', width: 48, depth: 38 });
  base.staticObjects = []; base.solids = []; base.routes = [];
  const model = new SceneEditorModel(base);
  const charge = model.create('charger', [-10, .08, 0]);
  const work = model.create('painted_floor_marker', [10, .015, 0]);
  const dropoff = model.create('station', [10, .5, 8]);
  assert.equal(model.setOperationalRole(charge, 'CHARGE'), true);
  assert.equal(model.setOperationalRole(work, 'WORK'), true);
  assert.equal(model.setOperationalRole(dropoff, 'DROPOFF'), true);
  assert.equal(model.setOperationalRole(charge, 'WORK'), false);
  assert.equal(operationalAnchors(model.scene).length, 3);
  const selection = { chargeId: charge, workId: work, dropoffId: dropoff };
  const clear = planOperationalPath(model.scene, selection);
  assert.equal(clear.ok, true, clear.reason);
  const wall = model.createWallSegment([0, -8], [0, 8]);
  assert.ok(wall);
  const detour = planOperationalPath(model.scene, selection);
  assert.equal(detour.ok, true, detour.reason);
  assert.ok(detour.distance > clear.distance + 2);
  model.delete(wall[0]);
  assert.equal(planOperationalPath(model.scene, selection).ok, true);
  const barrier = model.createWallSegment([0, -18], [0, 18]);
  assert.ok(barrier);
  const blocked = planOperationalPath(model.scene, selection);
  assert.equal(blocked.ok, false);
  assert.match(blocked.reason, /Нет прохода/);
  model.delete(barrier[0]);
  const restored = importSceneDocument(exportSceneDocument(model.history.present));
  assert.equal(new SceneEditorModel(base, restored.patch).scene.staticObjects.find(item => item.id === charge).operational_role, 'CHARGE');
  const zone = model.addZone('Уборка', [[-15, 8], [-11, 8], [-11, 12], [-15, 12]]);
  assert.equal(model.setZoneOperationalRole(zone, 'WORK'), true);
  assert.equal(planOperationalPath(model.scene, { ...selection, workId: zone, dropoffId: '' }).ok, true);
  assert.equal(model.setZoneOperationalRole(zone, 'DROPOFF'), false);
  model.delete(work);
  assert.match(planOperationalPath(model.scene, selection).reason, /WORK/);
});

test('поворотные прямоугольники используют footprint вместо AABB при столкновении', () => {
  const first = { position: [0, 1.5, 0], scale: [4, 3, .3], yaw: Math.PI / 4 };
  const nearAabbCorner = { position: [1.4, 1.5, 1.4], scale: [.4, 3, .4], yaw: 0 };
  assert.equal(solidsOverlap(first, nearAabbCorner), false);
});

test('назначение размещённого робота сохраняется, движется и блокируется стеной', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'ASSIGNMENT', width: 48, depth: 38 });
  base.staticObjects = []; base.solids = []; base.routes = []; base.people = [];
  const model = new SceneEditorModel(base);
  const robot = model.create('pallet_amr', [-10, .35, -4]);
  const charge = model.create('charger', [-10, .08, 0]);
  const work = model.create('painted_floor_marker', [10, .015, 0]);
  const dropoff = model.create('painted_floor_marker', [10, .015, 8]);
  model.setOperationalRole(charge, 'CHARGE'); model.setOperationalRole(work, 'WORK'); model.setOperationalRole(dropoff, 'DROPOFF');
  const selection = { chargeId: charge, workId: work, dropoffId: dropoff };
  assert.match(model.assignRobot(robot, selection, 1300, 1).reason, /1200/);
  assert.equal(model.assignRobot(robot, selection, 800, 1).ok, true);
  assert.equal(model.scene.editorAssignments[0].ok, true);
  assert.equal(model.scene.routes.length, 1);
  assert.equal(model.scene.routes[0].pickupWaypoint, planOperationalPath(model.scene, selection, .61).waypointIndices[1]);
  const simulation = createSimulation(model.scene);
  const start = [...simulation.robots[0].position];
  for (let index = 0; index < 30; index += 1) updateSimulation(simulation, .1, model.scene.solids);
  assert.ok(Math.hypot(simulation.robots[0].position[0] - start[0], simulation.robots[0].position[2] - start[2]) > .2);
  for (let index = 0; index < 1800; index += 1) updateSimulation(simulation, .1, model.scene.solids);
  assert.ok(simulation.trips >= 1, 'назначенный робот должен завершить цикл CHARGE → WORK → DROPOFF');
  const restored = new SceneEditorModel(base, importSceneDocument(exportSceneDocument(model.history.present)).patch);
  assert.equal(restored.scene.editorAssignments[0].ok, true);
  const wall = model.createWallSegment([0, -18], [0, 18]);
  assert.ok(wall);
  assert.equal(model.scene.editorAssignments[0].ok, false);
  assert.equal(model.scene.routes.length, 0);
  const stopped = createSimulation(model.scene);
  preserveOperationalRobotPositions(simulation, stopped, model.scene);
  assert.equal(stopped.robots[0].mode, 'blocked');
  assert.deepEqual(stopped.robots[0].position, simulation.robots[0].position);
  updateSimulation(stopped, 1, model.scene.solids);
  assert.deepEqual(stopped.robots[0].position, simulation.robots[0].position);
  model.undo();
  assert.equal(model.scene.editorAssignments[0].ok, true);
  const resumed = createSimulation(model.scene);
  preserveOperationalRobotPositions(stopped, resumed, model.scene);
  assert.deepEqual(resumed.robots[0].position, simulation.robots[0].position);
  assert.notEqual(resumed.robots[0].mode, 'blocked');
  model.delete(work);
  assert.equal(model.scene.editorAssignments[0].ok, false);
  assert.match(model.scene.editorAssignments[0].reason, /WORK/);
  model.undo();
  model.delete(robot);
  assert.equal(model.history.present.assignments.length, 0);
  const deleted = createSimulation(model.scene);
  preserveOperationalRobotPositions(resumed, deleted, model.scene);
  assert.equal(deleted.robots.length, 0);
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
  assert.deepEqual(scenePatchSummary(model.history.present), { objects: 0, created: 1, deleted: 0, robots: 0, zones: 0, rooms: 0, assignments: 0, economics: 0 });
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
