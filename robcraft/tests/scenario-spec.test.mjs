import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseWarehouseScenarioSpec } from '../src/integration/scenario-spec.js';
import { generateWorldFromScenarioSpec } from '../src/world/generator.js';
import { createSimulation, getSimulationReport, updateSimulation } from '../src/simulation.js';

const fixtureUrl = new URL('../../contracts/fixtures/scenario-spec-v1.golden.json', import.meta.url);
const golden = JSON.parse(readFileSync(fixtureUrl, 'utf8'));

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
  assert.ok(scene.routes.every(route => route.equipmentModelId === 'agv_pallet_qr'));
  assert.ok(scene.routes.every(route => route.modelCode === 'agv_pallet_qr'));
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
  assert.equal(report.equipmentModelId, 'agv_pallet_qr');
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
    () => parseWarehouseScenarioSpec({ ...golden, schema_version: 'scenario-spec-v2' }),
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
    assert.ok(result.report.robots.every(robot => robot.equipmentModelId === 'agv_pallet_qr'));
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
