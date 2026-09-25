import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  buildSimulationScene,
  createTimelineState,
  deterministicCapture,
  frameAt,
  hasCapacityWarning,
  parseSimulationBundle,
  reduceTimeline,
} from '../src/simulation2dModel.js';
import { SimulationApiSession } from '../src/simulationApi.js';
import { sceneBindingsV2 } from '../../robcraft/src/integration/scene-bindings.js';
import { parseScenarioSpec } from '../../robcraft/src/integration/scenario-spec.js';

const request = JSON.parse(await readFile(new URL('../../contracts/fixtures/simulation-request-v1.capacity-only.golden.json', import.meta.url), 'utf8'));
const report = JSON.parse(await readFile(new URL('../../contracts/fixtures/simulation-report-v1.capacity-only.golden.json', import.meta.url), 'utf8'));
const corrected = JSON.parse(await readFile(new URL('../../contracts/fixtures/simulation-report-v2.capacity-only.golden.json', import.meta.url), 'utf8'));
const golden = JSON.parse(await readFile(new URL('./fixtures/simulation-2d-v2.capacity-only.golden.json', import.meta.url), 'utf8'));
const warehouse = JSON.parse(await readFile(new URL('./fixtures/warehouse-2d-stage3.json', import.meta.url), 'utf8'));
const warehouseCapture = JSON.parse(await readFile(new URL('./fixtures/warehouse-2d-stage3.capture.json', import.meta.url), 'utf8'));

test('warehouse golden path shares zone, task and route identities with RobCraft', () => {
  const bundle = parseSimulationBundle(warehouse.request, warehouse.report);
  const scene = buildSimulationScene(bundle.spec);
  const parsed3d = parseScenarioSpec(bundle.spec);
  const bindings = sceneBindingsV2(bundle.spec);
  assert.equal(scene.kind, 'WAREHOUSE_TRANSPORT');
  assert.equal(scene.zones[0].id, parsed3d.zones[0].zone.id);
  assert.equal(scene.zones[0].label, parsed3d.zones[0].zone.name);
  assert.equal(scene.tasks[0].id, parsed3d.zones[0].scenario.taskId);
  assert.equal(scene.routes[0].id, parsed3d.zones[0].scenario.routeId);
  assert.equal(scene.tasks[0].pickupId, parsed3d.zones[0].scenario.pickupId);
  assert.equal(scene.tasks[0].dropoffId, parsed3d.zones[0].scenario.dropoffId);
  assert.equal(scene.tasks[0].id, bindings[0].tasks[0].taskId);
  assert.equal(scene.robots.length, 10);
  assert.ok(scene.robots.every((robot) => robot.zoneId === scene.zones[0].id
    && robot.taskId === scene.tasks[0].id && robot.routeId === scene.routes[0].id));
  assert.deepEqual(deterministicCapture(warehouse.request, warehouse.report, 5_000_000), warehouseCapture);
});

test('warehouse pallet visibly passes pickup, robot and dropoff stages in its own lane', () => {
  const bundle = parseSimulationBundle(warehouse.request, warehouse.report);
  const scene = buildSimulationScene(bundle.spec);
  const robot = scene.robots[0];
  const frames = Array.from({ length: 100 }, (_, index) => frameAt(scene, bundle, index * 200_000));
  const stages = new Set(frames.map((frame) => frame.robots[0].stage));
  assert.deepEqual(stages, new Set(['TO_PICKUP', 'LOADING', 'TO_DROPOFF', 'UNLOADING', 'RETURN', 'WAITING']));
  assert.equal(frames.find((frame) => frame.robots[0].stage === 'TO_DROPOFF').robots[0].cargoState, 'ON_ROBOT');
  assert.equal(frames.find((frame) => frame.robots[0].stage === 'UNLOADING').robots[0].cargoState, 'AT_DROPOFF');
  assert.ok(frames.every((frame) => frame.robots.every((item) => item.zoneId === robot.zoneId)));
  assert.equal(new Set(scene.robots.map((item) => item.points.waiting.y)).size, scene.robots.length);
  assert.deepEqual(frameAt(scene, bundle, 5_000_000), frameAt(buildSimulationScene(bundle.spec), bundle, 5_000_000));
});

test('multiple warehouse zones keep robots and tasks inside their own rectangles', () => {
  const spec = structuredClone(warehouse.request.scenario_spec);
  const secondZone = { ...spec.zones[0], zone_id: 'zone.second', label: 'Вторая зона' };
  const secondRoute = { ...spec.routes[0], route_id: 'route.second' };
  const secondTask = { ...spec.tasks[0], task_id: 'task.second', zone_id: secondZone.zone_id, route_ref: secondRoute.route_id };
  const secondFleet = { ...spec.fleet[0], fleet_id: 'fleet.second', zone_id: secondZone.zone_id, selected_fleet: 3 };
  spec.zones.push(secondZone);
  spec.routes.push(secondRoute);
  spec.tasks.push(secondTask);
  spec.fleet.push(secondFleet);
  const scene = buildSimulationScene(spec);
  const [first, second] = scene.zones;
  assert.ok(first.x + first.width < second.x);
  assert.equal(scene.robots.length, 13);
  for (const robot of scene.robots) {
    const zone = scene.zones.find((item) => item.id === robot.zoneId);
    const frame = frameAt(scene, { spec, report: warehouse.report }, 8_000_000).robots.find((item) => item.id === robot.id);
    assert.ok(frame.x > zone.x && frame.x < zone.x + zone.width);
    assert.ok(frame.y > zone.y && frame.y < zone.y + zone.height);
    assert.equal(scene.tasks.find((task) => task.id === robot.taskId).zoneId, robot.zoneId);
  }
  assert.equal(parseScenarioSpec(spec).zones[1].scenario.taskId, secondTask.task_id);
});

test('missing tasks or coordinates remain explicit and never become an invented route', () => {
  const original = structuredClone(warehouse.request.scenario_spec);
  const provided = structuredClone(original);
  provided.zones[0] = { ...provided.zones[0], geometry_source: 'PROVIDED', geometry_ref: 'plan.warehouse', assumption_ref: null };
  provided.routes[0] = { ...provided.routes[0], geometry_source: 'PROVIDED', geometry_ref: 'route.warehouse', assumption_ref: null };
  const scene = buildSimulationScene(provided);
  assert.equal(scene.zones[0].geometryLabel, 'Расположение условное');
  assert.equal(scene.routes[0].geometryLabel, 'Расположение условное');
  assert.deepEqual(scene.routes[0].analyticalDistance, original.routes[0].one_way_distance);
  assert.equal(scene.zones[0].geometryRef, 'plan.warehouse');
  const empty = structuredClone(original);
  empty.tasks = [];
  empty.routes = [];
  const waiting = buildSimulationScene(empty);
  assert.deepEqual(waiting.missingTasks, [empty.zones[0].zone_id]);
  assert.ok(frameAt(waiting, { spec: empty, report: warehouse.report }, 5_000_000).robots.every((robot) => robot.stage === 'WAITING' && robot.cargoState === null));
  assert.equal(frameAt(waiting, { spec: empty, report: warehouse.report }, 5_000_000).events.length, 0);
});

test('shared adapter rejects a fleet that cannot be safely drawn or rendered', () => {
  const spec = structuredClone(warehouse.request.scenario_spec);
  spec.fleet[0].selected_fleet = 101;
  assert.throws(() => buildSimulationScene(spec), /selected_fleet/);
  assert.throws(() => parseScenarioSpec(spec), /selected_fleet/);
});

test('capacity-only C23 report creates the deterministic golden 2D capture offline', () => {
  assert.equal(request.scenario_spec.finance, null);
  assert.deepEqual(deterministicCapture(request, corrected), golden);
  const bundle = parseSimulationBundle(request, report);
  assert.equal(bundle.report.sla.verdict, 'NOT_EVALUATED');
  assert.equal(bundle.report.engineering_claim, 'PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION');
});

test('corrected report uses demand as denominator and keeps historical reports readable', () => {
  assert.equal(parseSimulationBundle(request, corrected).report.capacity.denominator, 'REQUIRED_DEMAND');
  assert.equal(corrected.capacity.verdict, 'CONSISTENT');
  assert.equal(parseSimulationBundle(request, report).report.capacity.denominator, 'EXPECTED_EFFECTIVE_FLEET_CAPACITY');
});

test('timeline start, pause, stop, restart and speed are deterministic', () => {
  let state = createTimelineState('binding-a');
  state = reduceTimeline(state, { type: 'START' });
  state = reduceTimeline(state, { type: 'TICK', deltaMs: 100 });
  assert.equal(state.simulationTimeUs, 100000);
  state = reduceTimeline(state, { type: 'SET_SPEED', speed: 4 });
  state = reduceTimeline(state, { type: 'TICK', deltaMs: 100 });
  assert.equal(state.simulationTimeUs, 500000);
  state = reduceTimeline(state, { type: 'PAUSE' });
  assert.equal(reduceTimeline(state, { type: 'TICK', deltaMs: 100 }).simulationTimeUs, 500000);
  state = reduceTimeline(state, { type: 'RESTART' });
  assert.deepEqual({ status: state.status, time: state.simulationTimeUs, speed: state.speed, restart: state.restart }, { status: 'RUNNING', time: 0, speed: 4, restart: 1 });
  state = reduceTimeline(state, { type: 'STOP' });
  assert.equal(state.simulationTimeUs, 0);
  assert.throws(() => reduceTimeline(state, { type: 'SET_SPEED', speed: 3 }), /скорость/);
});

test('speed changes playback only and the same simulation time has the same report-bound frame', () => {
  const bundle = parseSimulationBundle(request, report);
  const scene = buildSimulationScene(bundle.spec);
  assert.deepEqual(frameAt(scene, bundle, 9000000), frameAt(scene, bundle, 9000000));
  const frame = frameAt(scene, bundle, 9000000);
  assert.equal(frame.scenarioRevisionId, request.scenario_spec.revision_id);
  assert.equal(frame.reportDigest, report.replay.report_content_digest);
  assert.equal(frame.seed, request.scenario_spec.seed);
  assert.ok(frame.events.every((event) => event.type === 'VISUAL_OPERATION'));
  assert.ok(frame.events.every((event) => !['FAILURE', 'CHARGING'].includes(event.operation)));
});

test('provided and synthetic geometry stay labelled and never rewrite analytical route distance', () => {
  const spec = structuredClone(request.scenario_spec);
  spec.zones[0] = { ...spec.zones[0], geometry_source: 'PROVIDED', geometry_ref: 'geometry.zone.terminal', assumption_ref: null };
  spec.routes = [{
    route_id: 'route.terminal', geometry_source: 'PROVIDED', geometry_ref: 'geometry.route.terminal', assumption_ref: null,
    one_way_distance: { numeric_encoding: 'DECIMAL_STRING', quantity_kind: 'LENGTH', value: '120', unit: 'm' },
  }];
  spec.tasks[0].route_ref = 'route.terminal';
  const before = structuredClone(spec.routes[0].one_way_distance);
  const scene = buildSimulationScene(spec);
  assert.equal(scene.zones[0].geometryLabel, 'PROVIDED_REFERENCE');
  assert.equal(scene.routes[0].geometryLabel, 'PROVIDED_REFERENCE');
  assert.deepEqual(scene.routes[0].analyticalDistance, before);
  assert.deepEqual(spec.routes[0].one_way_distance, before);
  assert.equal(scene.charging[0].status, 'AGGREGATE_ALLOWANCE_BADGE');
});

test('strict consumer rejects unknown versions, extra fields and stale report revisions', () => {
  assert.throws(() => parseSimulationBundle({ ...request, schema_version: 'simulation-request-v2' }, report), /версия/);
  assert.throws(() => parseSimulationBundle({ ...request, surprise: true }, report), /неизвестные поля/);
  assert.throws(() => parseSimulationBundle(request, { ...report, scenario_revision_id: 'calc_0000000000000000' }), /не связан/);
  assert.throws(() => parseSimulationBundle(request, { ...report, sla: { ...report.sla, verdict: 'PASS' } }), /PASS/);
});

test('warning and SLA presentation use authoritative report verdicts only', () => {
  assert.equal(hasCapacityWarning(report), false);
  assert.equal(hasCapacityWarning({ capacity: { verdict: 'DEVIATION', deviation_percent: '10.0001' } }), true);
  assert.equal(hasCapacityWarning({ capacity: { verdict: 'CONSISTENT', deviation_percent: '10' } }), false);
  assert.equal(report.sla.verdict, 'NOT_EVALUATED');
  const conditional = { ...report, sla: { ...report.sla, verdict: 'CONDITIONAL' } };
  assert.equal(conditional.sla.verdict, 'CONDITIONAL');
});

test('API session ignores a stale start response after scenario replacement', async () => {
  globalThis.document = { cookie: 'robodovod_csrf=test-token' };
  let resolveFirst;
  const first = new Promise((resolve) => { resolveFirst = resolve; });
  const terminal = (boundRequest) => ({
    ok: true,
    json: async () => ({
      schema_version: 'simulation-run-state-v1', request_id: boundRequest.request_id,
      tenant_id: boundRequest.tenant_id, project_id: boundRequest.project_id,
      scenario_revision_id: boundRequest.scenario_spec.revision_id, state: 'SUCCEEDED', report,
    }),
  });
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) return first;
    return terminal(request);
  };
  const session = new SimulationApiSession({ pollMs: 1 });
  const stale = session.start(request);
  const current = session.start(request);
  assert.equal((await current).state, 'SUCCEEDED');
  resolveFirst(terminal(request));
  assert.equal(await stale, null);
});

test('saved simulation uses run-scoped CSRF POST and reopens persisted report', async () => {
  globalThis.document = { cookie: 'robodovod_csrf=c23-token' };
  const requests = [];
  const state = {
    schema_version: 'simulation-run-state-v1', request_id: request.request_id,
    tenant_id: request.tenant_id, project_id: request.project_id,
    scenario_revision_id: request.scenario_spec.revision_id,
    state: 'SUCCEEDED', report: corrected,
  };
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return { ok: true, json: async () => state };
  };
  const session = new SimulationApiSession();
  const result = await session.start(request, () => {}, 'run.saved.c23');
  const reopened = await session.loadSaved(request, 'run.saved.c23');
  assert.equal(result.report.replay.report_content_digest, corrected.replay.report_content_digest);
  assert.equal(reopened.state, 'SUCCEEDED');
  assert.match(requests[0].url, /\/projects\/.*\/analysis-runs\/run.saved.c23$/);
  assert.equal(requests[0].options.headers['X-CSRF-Token'], 'c23-token');
  assert.equal(requests[0].options.credentials, 'include');
  assert.match(requests[1].url, /run.saved.c23\/request.c23.capacity-only$/);
});

test('component exposes controls, bindings and honest SLA/charging labels without client formulas', async () => {
  const source = await readFile(new URL('../src/components/Simulation2DReport.jsx', import.meta.url), 'utf8');
  for (const label of ['Старт', 'Пауза', 'Стоп', 'Перезапуск', 'Скорость', 'scenario', 'report', 'seed']) assert.match(source, new RegExp(label));
  assert.match(source, /Норматив времени не оценён/);
  assert.match(source, /зарядка учтена агрегированно/i);
  assert.match(source, /Координаты и движение роботов условные/);
  assert.match(source, /Предел расчётного парка/);
  assert.doesNotMatch(source, /NPV|CAPEX\s*[+*/-]|payback|fleet\s*=|capacity\s*=/i);
});
