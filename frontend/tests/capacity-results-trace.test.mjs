import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { createCapacityAnalysisClient } from '../src/capacityAnalysisApi.js';
import {
  assertCapacityResponse,
  formatServerQuantity,
  getCapacityResultsModel,
} from '../src/capacityResultsModel.js';

const quantity = (value, unit, quantity_kind = 'RATE') => ({
  value, unit, quantity_kind, numeric_encoding: 'DECIMAL_STRING',
});

function response(status = 'COMPLETE', selected = 9) {
  const completed = ['COMPLETE', 'WITH_ASSUMPTIONS'].includes(status);
  return {
    schema_version: 'capacity-analysis-response-v2',
    run_id: 'run.frontend.c12',
    input_revision: 'revision.frontend.c12',
    capacity: {
      schema_version: 'capacity-result-v1', process_id: 'process.warehouse.transport', status,
      value: completed ? {
        recommended_fleet: 9, selected_fleet: selected,
        nominal_capacity: quantity('13.10924369747899159663865546', 'pallet/h'),
        effective_capacity: quantity('9.176470588235294117647058822', 'pallet/h'),
        coverage: quantity('0.875', '1', 'FRACTION'),
        raw_load_ratio: quantity('1.142857142857', '1', 'FRACTION'),
        utilization: quantity('1', '1', 'FRACTION'), overloaded: true,
      } : null,
      blockers: completed ? [] : [{ code: 'c11-missing-speed', reason: 'MISSING_SAFE_FACT', severity: 'BLOCKER', field_refs: ['speed'], node_refs: [], decision_refs: ['K02'], message: 'Нет безопасной скорости' }],
      warnings: status === 'WITH_ASSUMPTIONS' ? [{ code: 'capacity-assumption', reason: 'UNAPPROVED_ASSUMPTION', severity: 'WARNING', field_refs: ['availability'], node_refs: [], decision_refs: ['K22'], message: 'Использовано утверждённое допущение' }] : [],
      trace_ref: 'trace.run.frontend.c12',
    },
    trace: {
      envelope: { schema_version: 'calculation-trace-v1', engine_version: 'capacity-analysis-service-v2', run_id: 'run.frontend.c12', input_revision: 'revision.frontend.c12', acquisition: 'PURCHASE', uncertainty: 'BASE', process_id: 'process.warehouse.transport', model_id: 'model.safe', position_id: 'position.safe' },
      versions: { catalog_version_id: 'catalog-v1' },
      provenance: [{ provenance_id: 'prov.user', kind: 'USER', confirmation_revision: 'revision.frontend.c12' }],
      inputs: [{ status: 'KNOWN', name: 'demand_per_day', raw_value: '1000', raw_unit: 'pallet/day', normalized_value: '1000', unit: 'pallet/day', quantity_kind: 'FLOW', numeric_encoding: 'DECIMAL_STRING', provenance_ref: 'prov.user' }],
      formula_nodes: completed ? [{ node_id: 'node.f04', formula_id: 'F04', formula_version: 'v1', source_refs: ['K22'], source_digest: `sha256:${'a'.repeat(64)}`, template_id: 'peak-availability-reserve', applicability_domain: 'active process', dependency_node_ids: [], input_refs: ['demand_per_day'] }] : [],
      conversions: [],
      intermediates: completed ? [{ value_id: 'value.nominal', node_id: 'node.f04', name: 'nominal_capacity', value: quantity('13.10924369747899159663865546', 'pallet/h'), parent_refs: ['demand_per_day'] }] : [],
      assumptions: [], constraints: [], roundings: [],
      results: [{ result_id: 'result.capacity', status, value: completed ? quantity('9', 'robot', 'COUNT') : null, supporting_node_ids: completed ? ['node.f04'] : [], capacity_basis: completed ? 'EFFECTIVE' : 'NOT_APPLICABLE' }],
      issues: [], replay: { canonical_input_digest: `sha256:${'b'.repeat(64)}`, trace_content_digest: `sha256:${'c'.repeat(64)}`, deterministic_seed: null }, runtime_metadata: { build_id: null, runtime_id: null },
    },
  };
}

test('complete and assumption snapshots preserve server decimal strings and units', () => {
  const complete = getCapacityResultsModel(response());
  const partial = getCapacityResultsModel(response('WITH_ASSUMPTIONS'));
  assert.equal(formatServerQuantity(complete.nominalCapacity), '13,11 паллет/ч');
  assert.equal(formatServerQuantity(complete.coverage), '87,5 %');
  assert.equal(formatServerQuantity(complete.utilization), '100 %');
  assert.equal(formatServerQuantity(quantity('0.990675', '1', 'FRACTION')), '99,07 %');
  assert.equal(formatServerQuantity(quantity('196.635', 'unit/h')), '196,64 ед./ч');
  assert.equal(formatServerQuantity(quantity('137.65', 'unit/h')), '137,65 ед./ч');
  assert.equal(complete.steps[0].outputs[0].value.value, complete.nominalCapacity.value);
  assert.equal(complete.steps[0].inputs[0].source, 'Ввод пользователя');
  assert.equal(partial.statusLabel, 'Выполнен с допущениями');
  assert.equal(partial.economics, null);
  assert.match(partial.economicsLabel, /не рассчитана/);
});

test('manual fleet, overload and blocked result are explicit without fallback values', () => {
  const manual = getCapacityResultsModel(response('COMPLETE', 7));
  assert.equal(manual.fleetMode, 'MANUAL');
  assert.equal(manual.recommendedFleet, 9);
  assert.equal(manual.selectedFleet, 7);
  assert.equal(manual.overloaded, true);
  const blocked = getCapacityResultsModel(response('BLOCKED'));
  assert.equal(blocked.hasCapacity, false);
  assert.equal(blocked.nominalCapacity, null);
  assert.equal(blocked.blockers[0].reason, 'MISSING_SAFE_FACT');
  assert.equal(blocked.steps.length, 0);
});

test('identity and expected revision checks reject stale or mixed snapshots', () => {
  assert.throws(() => assertCapacityResponse(response(), 'revision.changed'), /STALE_CAPACITY_RESPONSE/);
  const mixed = response();
  mixed.trace.envelope.process_id = 'process.other';
  assert.throws(() => assertCapacityResponse(mixed), /CAPACITY_PROCESS_MISMATCH/);
});

test('API adapter reads immutable endpoint and discards an older concurrent response', async () => {
  let resolveFirst;
  const calls = [];
  const fetchImpl = (path, options) => {
    calls.push({ path, options });
    if (calls.length === 1) return new Promise((resolve) => { resolveFirst = resolve; });
    return Promise.resolve({ ok: true, json: async () => response() });
  };
  const client = createCapacityAnalysisClient(fetchImpl);
  const older = client.read('run.old');
  const latest = await client.read('run.frontend.c12', 'revision.frontend.c12');
  resolveFirst({ ok: true, json: async () => response() });
  await assert.rejects(older, /STALE_CAPACITY_RESPONSE/);
  assert.equal(latest.run_id, 'run.frontend.c12');
  assert.equal(calls[1].path, '/api/v2/capacity-analyses/run.frontend.c12');
  assert.equal(calls[1].options.credentials, 'include');
});

test('create adapter preserves revision and CSRF while the component has no arithmetic fallback', async () => {
  let call;
  const client = createCapacityAnalysisClient(async (path, options) => {
    call = { path, options };
    return { ok: true, json: async () => response() };
  });
  await client.create({ input_revision: 'revision.frontend.c12' }, 'csrf-c12');
  assert.equal(call.path, '/api/v2/capacity-analyses');
  assert.equal(call.options.headers['X-CSRF-Token'], 'csrf-c12');
  const source = await readFile(new URL('../src/components/CapacityResultsTrace.jsx', import.meta.url), 'utf8');
  assert.match(source, /Участвует в расчёте|participationLabel/);
  assert.match(source, /не пересчитывает формулы/);
  assert.match(source, /Capacity source/);
  assert.doesNotMatch(source, /Math\.|parseFloat|parseInt|Number\(/);
});
