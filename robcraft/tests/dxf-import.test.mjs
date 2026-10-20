import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { generateWorld } from '../src/world/generator.js';
import { SceneEditorModel } from '../src/editor/editor.js';
import { parseRobcraftDxf } from '../src/editor/dxf-import.js';

const sample = name => readFileSync(new URL(`../../Разобрать/ROBODOVOD_CODEX_SOL6_EXECUTION_PACKAGE_2026-10-20/ROBODOVOD_CODEX_PACKAGE/03_ASSETS_READY/cad_samples/${name}_sample.dxf`, import.meta.url), 'utf8');

for (const name of ['warehouse', 'airport', 'clinic']) test(`предоставленный ${name} DXF создаёт редактируемую 2.5D-геометрию`, () => {
  const parsed = parseRobcraftDxf(sample(name), { wallLayers: ['WALLS'], obstacleLayers: ['OBSTACLES'], wallHeightM: 3 });
  assert.ok(parsed.objects.length > 10);
  assert.ok(parsed.objects.some(object => object.kind === 'wall'));
  assert.ok(parsed.objects.every(object => object.scale[1] > 0));
  const base = generateWorld({ template: 'warehouse', seed: `DXF-${name}`, width: Math.ceil(parsed.width), depth: Math.ceil(parsed.depth) });
  base.staticObjects = []; base.solids = []; base.routes = []; base.people = [];
  const model = new SceneEditorModel(base);
  assert.equal(model.importDxfObjects(parsed.objects, { file_name: `${name}.dxf`, unit_meters: parsed.unitMeters,
    wall_height_m: parsed.wallHeightM, wall_layers: parsed.wallLayers, obstacle_layers: parsed.obstacleLayers,
    unsupported_entities: parsed.unsupported, malformed_entities: parsed.malformed }), parsed.objects.length);
  assert.equal(model.history.present.cad.file_name, `${name}.dxf`);
  assert.equal(model.entities().length, parsed.objects.length);
  assert.ok(model.scene.solids.length >= parsed.objects.length);
});

test('неподдержанный CAD и отсутствующие единицы явно отклоняются', () => {
  assert.throws(() => parseRobcraftDxf('DWG', {}), /DXF/);
  assert.throws(() => parseRobcraftDxf(sample('warehouse'), { wallLayers: ['WALLS'], obstacleLayers: [], wallHeightM: 3, unitMeters: -1 }), /единицы|масштаб|слои/i);
  assert.throws(() => parseRobcraftDxf(sample('warehouse'), { wallLayers: ['ROUTES-ABSENT'], obstacleLayers: [], wallHeightM: 3 }), /слоях/);
});
