import test from 'node:test';
import assert from 'node:assert/strict';
import { EditorInventory } from '../src/editor/inventory.js';
import { mapEntityAt, mapPoint, mapZoomAt, validZonePolygon } from '../src/editor/map-view.js';
import { SceneEditorModel } from '../src/editor/editor.js';
import { exportSceneDocument, importSceneDocument, scenePatchHasChanges } from '../src/editor/scene-patch.js';
import { generateWorld } from '../src/world/generator.js';
import { BUILD_CATALOG } from '../src/editor/editor.js';
import { SCENE_ASSET_NAMES, decodeGlb } from '../src/core/glb-model.js';
import { readFile } from 'node:fs/promises';

test('каталог назначает слоты, пустая рука не очищает их, колесо переключает циклически', () => {
  const inventory = new EditorInventory();
  assert.equal(inventory.assign('rack'), true);
  assert.equal(inventory.held, 'rack');
  assert.equal(inventory.assign('charger'), true);
  assert.equal(inventory.active, 1);
  inventory.select(0);
  assert.equal(inventory.assign('wall'), true);
  assert.equal(inventory.slots[0], 'wall');
  inventory.select(null);
  assert.equal(inventory.held, null);
  assert.equal(inventory.slots[0], 'wall');
  assert.equal(inventory.cycle(1), 0);
  assert.equal(inventory.held, 'wall');
  assert.equal(inventory.slots.length, 9);
  const full = new EditorInventory(Array(9).fill('rack'), 0);
  assert.equal(full.assign('wall'), false);
  full.select(4);
  assert.equal(full.assign('wall'), true);
  assert.equal(full.slots[4], 'wall');
});

test('пять независимых стоек, удаление пустой рукой, undo и сохранение проекта с хотбаром', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'HOTBAR-ROUNDTRIP' });
  const model = new SceneEditorModel(base);
  const inventory = new EditorInventory();
  inventory.assign('rack');
  const ids = Array.from({ length: 5 }, (_, index) => model.create(inventory.held, [80 + index * 4, 2.35, 80]));
  assert.equal(new Set(ids).size, 5);
  assert.equal(inventory.held, 'rack');
  inventory.select(null);
  assert.equal(model.delete(ids[2]), true);
  assert.equal(model.history.present.created.length, 4);
  model.undo();
  assert.equal(model.history.present.created.length, 5);
  const restored = importSceneDocument(exportSceneDocument(model.history.present, inventory.toJSON()));
  assert.deepEqual(restored.inventory, inventory.toJSON());
  assert.equal(new SceneEditorModel(base, restored.patch).history.present.created.length, 5);
});

test('2D план использует координаты той же сцены и находит установленный экземпляр', () => {
  const rect = { left: 10, top: 20, width: 480, height: 380 };
  assert.deepEqual(mapPoint(250, 210, rect, 48, 38), [0, 0]);
  const entity = { id: 'user:rack:1', position: [2, 2, 3], scale: [2, 4, 2] };
  assert.equal(mapEntityAt([2, 3], [entity]), entity);
  assert.equal(mapEntityAt([10, 10], [entity]), null);
});

test('масштаб закреплён под курсором, панорамирование меняет координаты и не меняет объекты', () => {
  const rect = { left: 10, top: 20, width: 480, height: 380 };
  const view = { zoom: 1, panX: 0, panZ: 0 };
  const before = mapPoint(330, 250, rect, 48, 38, view);
  const zoomed = mapZoomAt(view, 2, 330, 250, rect, 48, 38);
  assert.deepEqual(mapPoint(330, 250, rect, 48, 38, zoomed), before);
  assert.equal(mapZoomAt(zoomed, 10, 330, 250, rect, 48, 38).zoom, 4);
  assert.equal(mapZoomAt(view, .01, 330, 250, rect, 48, 38).zoom, .5);
  assert.notDeepEqual(mapPoint(250, 210, rect, 48, 38, { zoom: 1, panX: 3, panZ: -2 }), [0, 0]);
});

test('визуальный полигон сохраняется в ScenePatch, допускает undo и отвергает пересечение', () => {
  const base = generateWorld({ template: 'warehouse', seed: 'ZONE-ROUNDTRIP' });
  const model = new SceneEditorModel(base);
  const points = [[0, 0], [6, 0], [6, 4], [0, 4]];
  assert.equal(validZonePolygon(points, base.config.width, base.config.depth), true);
  assert.equal(validZonePolygon([[0, 0], [6, 4], [0, 4], [6, 0]], base.config.width, base.config.depth), false);
  const id = model.addZone('Зона приёмки', points);
  assert.ok(id?.startsWith('zone:'));
  assert.deepEqual(model.scene.editorZones[0].points, points);
  assert.equal(scenePatchHasChanges(model.history.present), true);
  const restored = importSceneDocument(exportSceneDocument(model.history.present));
  assert.deepEqual(restored.patch.zones[0].points, points);
  assert.equal(model.deleteZone(id), true);
  assert.equal(model.scene.editorZones.length, 0);
  model.undo();
  assert.equal(model.scene.editorZones.length, 1);
});

test('каждый указанный GLB доступен в каталоге и декодируется RobCraft', async () => {
  const kinds = new Set(BUILD_CATALOG.map(item => item.kind));
  for (const name of SCENE_ASSET_NAMES) {
    assert.ok(kinds.has(name), `Нет каталога для ${name}`);
    const file = await readFile(new URL(`../../frontend/public/scene-assets/${name}.glb`, import.meta.url));
    const groups = decodeGlb(file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength));
    assert.ok(groups.length && groups.every(group => group.vertices.length > 0), name);
  }
});
