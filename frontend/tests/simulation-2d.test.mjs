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

const request = JSON.parse(await readFile(new URL('../../contracts/fixtures/simulation-request-v1.capacity-only.golden.json', import.meta.url), 'utf8'));
const report = JSON.parse(await readFile(new URL('../../contracts/fixtures/simulation-report-v1.capacity-only.golden.json', import.meta.url), 'utf8'));
const corrected = JSON.parse(await readFile(new URL('../../contracts/fixtures/simulation-report-v2.capacity-only.golden.json', import.meta.url), 'utf8'));
const golden = JSON.parse(await readFile(new URL('./fixtures/simulation-2d-v2.capacity-only.golden.json', import.meta.url), 'utf8'));

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
  assert.match(source, /NOT_EVALUATED · SLA не оценён/);
  assert.match(source, /зарядка учтена агрегированно/i);
  assert.match(source, /Координаты и движение роботов условные/);
  assert.match(source, /Предел парка C11/);
  assert.doesNotMatch(source, /NPV|CAPEX\s*[+*/-]|payback|fleet\s*=|capacity\s*=/i);
});
