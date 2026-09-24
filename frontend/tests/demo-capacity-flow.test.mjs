import test from 'node:test';
import assert from 'node:assert/strict';
import { buildDemoCapacityRequest, demoCandidates, DEMO_MODELS, DEMO_PROFILES } from '../src/demoCapacityFlow.js';
import { createWarehouseDemoDraft, confirmRoleAssumption, serializeDraft } from '../src/processRoleIntakeV2.js';

const mule = {
  model_id: '4f866b44-1052-59cc-aa0d-ed1e80729f35',
  organizer_id: 'ecd7d582-b342-449a-b43b-66288d159a32',
  position_id: 'position.mule', calculation_ready: true,
  calculation_profile: 'TRANSPORT_CYCLE_V1', source_row_number: 20,
};
const cleaner = {
  model_id: '1265ce8a-b4e9-56bb-b7ed-b933591445a6',
  organizer_id: '446c5207-a099-45e0-b615-afd60de08589',
  position_id: 'position.mark', calculation_ready: true,
  calculation_profile: 'CLEANING_AREA_V1', source_row_number: 21,
};
const q = (name, value, unit) => ({
  status: 'KNOWN', name, raw_value: value, normalized_value: value,
  raw_unit: unit, unit, quantity_kind: 'RATE', provenance_ref: 'conversion.1',
});
const normalized = {
  response: {
    input_revision: 'draft.1', role_pool: { roles: [] }, normalized_processes: [{
      active: true, process_id: 'process.warehouse.transport', input_revision: 'draft.1',
      scope: 'TRANSPORT_CYCLE', route_distance: q('one_way_distance', '120', 'm'),
      explicit_batch: q('units_per_trip', '1', 'unit/trip'),
    }],
  },
};

test('demo candidates stay within authored model identities and physical profile', () => {
  assert.deepEqual(demoCandidates([mule, cleaner], 'TRANSPORT_CYCLE'), [mule]);
  assert.deepEqual(demoCandidates([mule, cleaner], 'CLEANING_AREA'), [cleaner]);
  assert.deepEqual(demoCandidates([mule, cleaner], 'REFERENCE_ONLY'), []);
  assert.deepEqual(demoCandidates([{ ...mule, organizer_id: undefined }], 'TRANSPORT_CYCLE'), []);
});

test('every selectable demo identity has visible source, assumptions and unknowns', () => {
  assert.deepEqual(Object.keys(DEMO_PROFILES).sort(), Object.keys(DEMO_MODELS).sort());
  for (const profile of Object.values(DEMO_PROFILES)) {
    assert.match(profile.sourceUrl, /^https:\/\//);
    assert.ok(profile.published && profile.assumptions && profile.unknown);
  }
});

test('preliminary request requires acknowledgement, project and explicit exchange', () => {
  const args = { normalized, projectId: 'project.1', processId: 'process.warehouse.transport',
    position: mule, exchangeSeconds: '90', acknowledged: true };
  const request = buildDemoCapacityRequest(args);
  assert.equal(request.execution_mode, 'PRELIMINARY_DEMO');
  assert.equal(request.model_id, mule.model_id);
  assert.notEqual(request.model_id, mule.organizer_id);
  assert.equal(request.demo_assumptions_confirmed, true);
  assert.equal(request.process.exchange.total_time.normalized_value, '90');
  assert.equal(request.provenance[0].kind, 'ASSUMPTION');
  assert.throws(() => buildDemoCapacityRequest({ ...args, acknowledged: false }), /Подтвердите/);
  assert.throws(() => buildDemoCapacityRequest({ ...args, projectId: null }), /проект/);
  assert.throws(() => buildDemoCapacityRequest({ ...args, exchangeSeconds: '' }), /время/);
  assert.throws(() => buildDemoCapacityRequest({ ...args, position: cleaner }), /профилю/);
});

test('cleaning demo exposes one pass per day rather than inventing vendor availability', () => {
  const cleaning = structuredClone(normalized);
  cleaning.response.normalized_processes[0] = {
    active: true, process_id: 'process.warehouse.cleaning', input_revision: 'draft.1',
    scope: 'CLEANING_AREA', demand: q('demand_per_day', '10000', 'm2/day'),
  };
  const request = buildDemoCapacityRequest({ normalized: cleaning, projectId: 'project.1',
    processId: 'process.warehouse.cleaning', position: cleaner, acknowledged: true });
  assert.equal(request.cleaning_area.normalized_value, '10000');
  assert.equal(request.cleaning_frequency.normalized_value, '1');
  assert.equal(request.availability, undefined);
});

test('organizer warehouse preset requires explicit salary confirmation', () => {
  const draft = createWarehouseDemoDraft();
  const receiving = draft.processes.find((item) => item.code === 'warehouse_receiving_shipping');
  assert.equal(receiving.demand, '2000');
  assert.equal(receiving.distance, '120');
  assert.throws(() => serializeDraft(draft), /INTAKE_DRAFT_INVALID/);
  const confirmed = confirmRoleAssumption(draft, draft.roles[0].roleId);
  const request = serializeDraft(confirmed);
  const input = request.processes.find((item) => item.process_code === 'warehouse_receiving_shipping');
  assert.equal(input.demand.provenance.source, 'ASSUMPTION');
  assert.equal(input.route_distance.provenance.source, 'ASSUMPTION');
  assert.equal(request.roles[0].headcount.provenance.source, 'ASSUMPTION');
  assert.equal(request.roles[0].monthly_gross_salary.provenance.source, 'ASSUMPTION');
  assert.equal(request.roles[0].monthly_gross_salary.provenance.user_confirmed, true);
});
