import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseScenarioSpec } from '../src/integration/scenario-spec.js';
import { generateWorldFromScenarioSpec, generateWorldsFromScenarioSpec } from '../src/world/generator.js';
import { createSimulation, updateSimulation } from '../src/simulation.js';

const golden = JSON.parse(readFileSync(new URL('../../contracts/fixtures/scenario-spec-v1.golden.json', import.meta.url), 'utf8'));

function zonalSpec() {
  const spec = structuredClone(golden);
  spec.revision_id = 'calc_abcdef0123456789';
  spec.zones = [
    { ...spec.zones[0], id: 'transport', name: 'Приёмка', demand_per_day: 480 },
    { id: 'cleaning', name: 'Торговый зал', process_type: 'cleaning', cargo_type: 'pallets', status: 'RECOMMENDED', demand_per_day: 2400, avg_distance_m: 40, aisle_width_m: 1.5, polygon: null },
    { id: 'palletizing', name: 'Конец линии', process_type: 'palletizing', cargo_type: 'cases', status: 'RECOMMENDED', demand_per_day: 720, avg_distance_m: 10, aisle_width_m: 2, polygon: null },
    { id: 'unsupported', name: 'Без оборудования', process_type: 'transport', cargo_type: 'carts', status: 'NO_ELIGIBLE_EQUIPMENT', demand_per_day: 20, avg_distance_m: 30, aisle_width_m: 2, polygon: null },
  ];
  spec.fleet = [
    { ...spec.fleet[0], zone_id: 'transport', quantity: 3 },
    { zone_id: 'cleaning', equipment_model_id: 'synthetic-cleaner', visual_profile: 'service-cleaner', quantity: 2, max_speed_m_s: 1.2, payload_kg: 0 },
    { zone_id: 'palletizing', equipment_model_id: 'synthetic-palletizer', visual_profile: 'palletizer-cell', quantity: 2, max_speed_m_s: 0, payload_kg: 21 },
  ];
  spec.task_profiles = [
    { ...spec.task_profiles[0], zone_id: 'transport', demand_per_day: 480 },
    { zone_id: 'cleaning', kind: 'cleaning', demand_per_day: 2400, units_per_trip: 100, exchange_time_s: 1 },
    { zone_id: 'palletizing', kind: 'palletizing', demand_per_day: 720, units_per_trip: 1, exchange_time_s: 2 },
  ];
  return spec;
}

test('многозонный контракт отделяет поддержанные сцены от зон без оборудования', () => {
  const spec = zonalSpec(); const before = JSON.stringify(spec);
  const parsed = parseScenarioSpec(spec);
  assert.equal(parsed.zones.length, 4);
  assert.deepEqual(parsed.zones.map(zone => zone.supported), [true, true, true, false]);
  assert.equal(parsed.zones.at(-1).reason, 'NO_ELIGIBLE_EQUIPMENT');
  assert.equal(JSON.stringify(spec), before);
  assert.ok(Object.isFrozen(parsed.spec));
});

test('каждая поддержанная зона получает отдельную точную концептуальную сцену', () => {
  const worlds = generateWorldsFromScenarioSpec(zonalSpec());
  const supported = worlds.zones.filter(zone => zone.supported);
  assert.equal(supported.length, 3);
  for (const entry of supported) {
    const fleet = worlds.spec.fleet.find(item => item.zone_id === entry.zone.id);
    assert.equal(entry.scene.routes.length, fleet.quantity);
    assert.ok(entry.scene.routes.every(route => route.equipmentModelId === fleet.equipment_model_id));
    assert.equal(entry.scene.scenario.zoneId, entry.zone.id);
    assert.equal(entry.scene.conceptualZone, true);
  }
  assert.equal(worlds.zones.at(-1).scene, null);
});

test('уборка использует coverage-маршрут, а паллетизация выполняет стационарный цикл', () => {
  const worlds = generateWorldsFromScenarioSpec(zonalSpec());
  const cleaning = worlds.zones.find(entry => entry.zone.id === 'cleaning').scene;
  assert.ok(cleaning.routes[0].points.length > 10);
  assert.equal(cleaning.routes[0].robotType, 'cleaning-robot');
  const palletizing = worlds.zones.find(entry => entry.zone.id === 'palletizing').scene;
  assert.equal(palletizing.routes[0].stationaryCycle, true);
  assert.equal(palletizing.routes[0].robotType, 'palletizer-cell');
  const simulation = createSimulation(palletizing);
  for (let elapsed = 0; elapsed < 130; elapsed += .25) updateSimulation(simulation, .25, palletizing.solids);
  assert.ok(simulation.trips > 0, 'стационарная ячейка должна завершать расчётные циклы');
  assert.equal(simulation.zoneId, 'palletizing');
  assert.equal(simulation.processType, 'palletizing');
});

test('клиническая доставка строит hospital-сцену с точной моделью', () => {
  const spec = structuredClone(golden);
  spec.template = 'hospital';
  spec.zones[0] = { ...spec.zones[0], process_type: 'delivery', cargo_type: 'deliveries', name: 'Клиническая доставка' };
  spec.fleet[0] = { ...spec.fleet[0], equipment_model_id: 'synthetic-delivery', visual_profile: 'medical-delivery', quantity: 2, max_speed_m_s: 1.2, payload_kg: 10 };
  spec.task_profiles[0] = { ...spec.task_profiles[0], kind: 'delivery', exchange_time_s: 120 };
  const scene = generateWorldFromScenarioSpec(spec);
  assert.equal(scene.config.template, 'hospital');
  assert.equal(scene.routes.length, 2);
  assert.ok(scene.routes.every(route => route.robotType === 'medical-cart' && route.equipmentModelId === 'synthetic-delivery'));
});

test('если поддержанных 3D-зон нет, fallback содержит явную причину', () => {
  const spec = zonalSpec();
  spec.zones = [spec.zones.at(-1)]; spec.fleet = []; spec.task_profiles = [];
  assert.throws(() => generateWorldFromScenarioSpec(spec), /NO_ELIGIBLE_EQUIPMENT/);
});
