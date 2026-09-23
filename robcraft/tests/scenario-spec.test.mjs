import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseScenarioSpec, parseWarehouseScenarioSpec } from '../src/integration/scenario-spec.js';
import { generateWorldFromScenarioSpec } from '../src/world/generator.js';
import { buildRendererReport, createSimulation, getSimulationReport, updateSimulation } from '../src/simulation.js';

const fixtureUrl = new URL('../../contracts/fixtures/scenario-spec-v1.golden.json', import.meta.url);
const golden = JSON.parse(readFileSync(fixtureUrl, 'utf8'));
const v2FixtureUrl = new URL('../../contracts/fixtures/scenario-spec-v2.capacity-only-cleaner.golden.json', import.meta.url);
const v2Golden = JSON.parse(readFileSync(v2FixtureUrl, 'utf8'));
const c23FixtureUrl = new URL('../../contracts/fixtures/simulation-report-v1.capacity-only.golden.json', import.meta.url);
const c23Golden = JSON.parse(readFileSync(c23FixtureUrl, 'utf8'));

function scenarioVariant({ quantity = 1, demandPerDay = 800, unitsPerTrip = 1, exchangeTimeS = 45 } = {}) {
  const spec = structuredClone(golden);
  spec.revision_id = `calc_${String(quantity).padStart(16, '0')}`;
  spec.seed = `STAGE-B-WAREHOUSE-${quantity}`;
  spec.fleet[0].quantity = quantity;
  spec.zones[0].demand_per_day = demandPerDay;
  spec.task_profiles[0].demand_per_day = demandPerDay;
  spec.task_profiles[0].units_per_trip = unitsPerTrip;
  spec.task_profiles[0].exchange_time_s = exchangeTimeS;
  return spec;
}

function run(spec, seconds, delta = .25) {
  const scene = generateWorldFromScenarioSpec(spec);
  const simulation = createSimulation(scene);
  simulation.people = [];
  let longestStall = 0;
  let stalled = 0;
  let trips = 0;
  for (let elapsed = 0; elapsed < seconds; elapsed += delta) {
    updateSimulation(simulation, delta, scene.solids);
    if (simulation.trips === trips) {
      stalled += delta;
      longestStall = Math.max(longestStall, stalled);
    } else {
      trips = simulation.trips;
      stalled = 0;
    }
  }
  return { scene, simulation, report: getSimulationReport(simulation), longestStall };
}

test('golden ScenarioSpec создаёт точную модель и полный парк без смешивания', () => {
  const before = JSON.stringify(golden);
  const parsed = parseWarehouseScenarioSpec(golden);
  const scene = generateWorldFromScenarioSpec(golden);
  assert.equal(parsed.quantity, 11);
  assert.equal(scene.routes.length, 11);
  assert.equal(scene.config.robotCount, 11);
  assert.equal(scene.scenario.revisionId, golden.revision_id);
  assert.ok(scene.routes.every(route => route.equipmentModelId === 'synthetic-transport-heavy'));
  assert.ok(scene.routes.every(route => route.modelCode === 'synthetic-transport-heavy'));
  assert.ok(scene.routes.every(route => route.robotType === 'pallet-amr'));
  assert.ok(scene.routes.every(route => route.speed === .8));
  assert.ok(scene.routes.every(route => route.maxLoadKg === 1500));
  assert.equal(JSON.stringify(golden), before, 'адаптер не должен мутировать входной snapshot');
  assert.ok(Object.isFrozen(scene.scenarioSpec));
});

test('контракт снимает прежний предел 8 и расширяет парковочную зону для полного парка', () => {
  const scene = generateWorldFromScenarioSpec(scenarioVariant({ quantity: 25 }));
  assert.equal(scene.routes.length, 25);
  assert.equal(scene.config.robotCount, 25);
  assert.ok(scene.config.width >= 50);
  assert.equal(new Set(scene.routes.map(route => route.points[0].join(':'))).size, 25);
});

test('спрос и units_per_trip задают частоту заявок и выполненные единицы', () => {
  const spec = scenarioVariant({ quantity: 2, demandPerDay: 960, unitsPerTrip: 4, exchangeTimeS: 1 });
  const demandScene = generateWorldFromScenarioSpec(spec);
  const demandSimulation = createSimulation(demandScene);
  demandSimulation.people = [];
  assert.equal(demandSimulation.taskQueue.length, 1);
  assert.equal(demandSimulation.robots.filter(robot => robot.activeTask).length, 0);
  updateSimulation(demandSimulation, .1, demandScene.solids);
  assert.equal(demandSimulation.robots.filter(robot => robot.activeTask).length, 1);
  assert.equal(demandSimulation.generatedTasks, 1);
  updateSimulation(demandSimulation, 359.8, demandScene.solids);
  assert.equal(demandSimulation.generatedTasks, 1);
  updateSimulation(demandSimulation, .1, demandScene.solids);
  assert.equal(demandSimulation.generatedTasks, 2);

  const { scene, simulation, report } = run(spec, 900);
  assert.equal(scene.scenario.taskIntervalS, 360);
  assert.equal(simulation.taskIntervalS, 360);
  assert.equal(report.tasks.unitsPerTrip, 4);
  assert.equal(report.tasks.completedUnits, report.tasks.completed * 4);
  assert.equal(report.tasks.requiredUnitsPerHour, 40);
  assert.equal(report.revisionId, spec.revision_id);
  assert.equal(report.equipmentModelId, 'synthetic-transport-heavy');
});

test('экономически неприемлемый технический вариант визуализируется без смены статуса', () => {
  const spec = scenarioVariant({ quantity: 1, demandPerDay: 24 });
  spec.zones[0].status = 'NO_ACCEPTABLE_ECONOMICS';
  spec.economics.status = 'NOT_ACCEPTABLE';
  spec.assumptions.push({
    code: 'VISUALIZATION_ONLY_NOT_RECOMMENDATION',
    message: 'Только визуализация, не рекомендация'
  });
  const parsed = parseWarehouseScenarioSpec(spec);
  const scene = generateWorldFromScenarioSpec(spec);

  assert.equal(parsed.visualizationOnly, true);
  assert.equal(parsed.quantity, 1);
  assert.equal(scene.scenario.visualizationOnly, true);
  assert.equal(scene.scenarioSpec.zones[0].status, 'NO_ACCEPTABLE_ECONOMICS');
  assert.equal(scene.scenarioSpec.economics.status, 'NOT_ACCEPTABLE');
});

test('неизвестная версия, лишние поля и неподдерживаемый процесс отклоняются явно', () => {
  assert.throws(
    () => parseWarehouseScenarioSpec({ ...golden, schema_version: 'scenario-spec-v3' }),
    /Неподдерживаемая версия/
  );
  assert.throws(
    () => parseWarehouseScenarioSpec({ ...golden, renderer_internal: {} }),
    /неизвестные поля/
  );
  const nested = structuredClone(golden);
  nested.economics.renderer_internal = 1;
  assert.throws(() => parseWarehouseScenarioSpec(nested), /неизвестные поля/);
  const unsupported = structuredClone(golden);
  unsupported.zones[0].process_type = 'cleaning';
  assert.throws(() => parseWarehouseScenarioSpec(unsupported), /transport-зону/);
  const unsupportedTask = structuredClone(golden);
  unsupportedTask.task_profiles[0].kind = 'cleaning';
  assert.throws(() => parseWarehouseScenarioSpec(unsupportedTask), /task kind/);
  const inconsistentDemand = structuredClone(golden);
  inconsistentDemand.task_profiles[0].demand_per_day += 1;
  assert.throws(() => parseWarehouseScenarioSpec(inconsistentDemand), /Спрос task_profile/);
});

test('ScenarioSpec v2 использует operating window вместо 24h shortcut и не считает finance', () => {
  const spec = structuredClone(v2Golden);
  spec.operating_windows[0].duration.value = '8';
  const before = JSON.stringify(spec);
  const parsed = parseScenarioSpec(spec);
  const scenario = parsed.zones[0].scenario;
  assert.equal(scenario.operatingHoursPerDay, 8);
  assert.equal(scenario.taskIntervalS, 8 * 3600 * 100 / 51000);
  assert.equal(scenario.financeStatus, 'NOT_PROVIDED');
  assert.equal(scenario.geometryMode, 'SYNTHETIC');
  assert.equal(JSON.stringify(spec), before);
  assert.ok(Object.isFrozen(parsed.spec));

  const scene = generateWorldFromScenarioSpec(spec);
  const simulation = createSimulation(scene);
  const report = getSimulationReport(simulation);
  assert.equal(report.tasks.requiredUnitsPerHour, 6375);
  assert.equal(report.fleet.utilizationBasis, 'MOVING_TIME');
  assert.equal(report.fleet.productiveUtilizationStatus, 'NOT_EVALUATED_LOCAL_TIME_STEP');
});

test('provided analytical route survives representative rendering and renderer report is honestly bound', () => {
  const spec = structuredClone(v2Golden);
  spec.zones[0] = { ...spec.zones[0], geometry_source: 'PROVIDED', geometry_ref: 'geometry.zone.terminal', assumption_ref: null };
  spec.routes.push({ route_id: 'route.terminal', geometry_source: 'PROVIDED', one_way_distance: { value: '123', unit: 'm', quantity_kind: 'DISTANCE', numeric_encoding: 'DECIMAL_STRING' }, geometry_ref: 'geometry.route.terminal', assumption_ref: null });
  spec.tasks[0].route_ref = 'route.terminal';
  const scene = generateWorldFromScenarioSpec(spec);
  const simulation = createSimulation(scene);
  const renderer = buildRendererReport(simulation, c23Golden);
  assert.equal(scene.scenario.analyticalRoute.one_way_distance.value, '123');
  assert.equal(spec.routes[0].one_way_distance.value, '123');
  assert.equal(renderer.bindings.authoritative_report_digest, c23Golden.replay.report_content_digest);
  assert.equal(renderer.geometry.source, 'PROVIDED');
  assert.equal(renderer.geometry.analytical_distance_value, '123');
  assert.equal(renderer.energy.unit, 'ARBITRARY_RENDERER_UNIT');
  assert.equal(renderer.model_status.sla, 'NOT_EVALUATED_USE_C23_REPORT');
  assert.equal(renderer.utilization.productive_percent, null);
});

test('ScenarioSpec v2 rejects unknown fields without implicit downgrade', () => {
  assert.throws(() => parseScenarioSpec({ ...v2Golden, renderer_internal: {} }), /неизвестные поля/);
  const nested = structuredClone(v2Golden);
  nested.tasks[0].batch.renderer_internal = true;
  assert.throws(() => parseScenarioSpec(nested), /неизвестные поля/);
  assert.throws(() => parseScenarioSpec({ ...v2Golden, schema_version: 'scenario-spec-v3' }), /Неподдерживаемая версия/);
});

test('golden-парки 1…12 выполняют задания без длительного operational deadlock', () => {
  const completed = [];
  for (let quantity = 1; quantity <= 12; quantity += 1) {
    const result = run(
      scenarioVariant({ quantity, demandPerDay: 4800, unitsPerTrip: 1, exchangeTimeS: 4 }),
      1800
    );
    completed.push(result.report.tasks.completed);
    assert.ok(result.report.tasks.completed > 0, `парк ${quantity}: нет завершённых заданий`);
    assert.ok(result.longestStall < 900, `парк ${quantity}: простой ${result.longestStall} с`);
    assert.ok(result.report.tasks.queued <= quantity * 2, `парк ${quantity}: очередь вышла за предел`);
    assert.ok(result.report.robots.every(robot => robot.equipmentModelId === 'synthetic-transport-heavy'));
  }
  // В этой сцене диспетчер намеренно ограничивает одновременное движение двумя
  // AMR, поэтому помашинная монотонность не является обещанием контракта. Полный
  // рассчитанный golden-парк при этом не должен работать хуже одиночного AMR.
  assert.ok(completed[10] >= completed[0], `golden-парк: ${completed[10]} задач против ${completed[0]}`);
});

test('при достаточной мощности низкий спрос не создаёт неограниченную очередь', () => {
  const { report } = run(
    scenarioVariant({ quantity: 4, demandPerDay: 96, unitsPerTrip: 1, exchangeTimeS: 2 }),
    7200
  );
  assert.ok(report.tasks.completed > 0);
  assert.ok(report.tasks.queued <= 1, JSON.stringify(report.tasks));
  assert.equal(report.tasks.unservedDemandTasks, 0);
});
