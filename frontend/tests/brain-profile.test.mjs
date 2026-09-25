import test from 'node:test';
import assert from 'node:assert/strict';
import { capacityKpiDiff, makeBrainDraft, profileInputDiff } from '../src/brainProfile.js';
import { brainCandidates } from '../src/demoCapacityFlow.js';

function profile(overrides = {}) {
  const entries = { object_type: 'retail', process_type: 'transport', operations_per_day: '220', shifts_count: '2',
    shift_hours: '11', operating_days: '365', avg_distance_m: '120', units_per_trip: '1', exchange_seconds: '90', ...overrides };
  return { fields: Object.fromEntries(Object.entries(entries).map(([key, value]) => [key, { value, provenance: 'user', confirmed_by_user: true }])) };
}

test('220 pallets and 120 m reach current v2 normalization request without invented salary', () => {
  const { request } = makeBrainDraft(profile());
  const process = request.processes.find((item) => item.active);
  assert.equal(process.demand.value, '220');
  assert.equal(process.route_distance.value, '120');
  assert.equal(process.explicit_batch.value, '1');
  assert.equal(request.roles.length, 0);
});

test('unconfirmed quantity cannot become a calculation input', () => {
  const input = profile();
  input.fields.units_per_trip.confirmed_by_user = false;
  assert.throws(() => makeBrainDraft(input), /INTAKE_DRAFT_INVALID/);
});

test('what-if changes only named input and keeps separate run identity', () => {
  const first = profile();
  const second = profile({ operations_per_day: '260' });
  assert.deepEqual(profileInputDiff(first, second), [{ key: 'operations_per_day', from: '220', to: '260' }]);
});

test('what-if compares saved capacity KPI values without recalculating them', () => {
  const previous = { capacity: { value: { recommended_fleet: 3, effective_capacity: { value: '240', unit: 'pallet/day' } } } };
  const current = { capacity: { value: { recommended_fleet: 4, effective_capacity: { value: '300', unit: 'pallet/day' } } } };
  assert.deepEqual(capacityKpiDiff(previous, current), [
    { key: 'recommended_fleet', label: 'Рекомендованный парк', from: '3', to: '4' },
    { key: 'effective_capacity', label: 'Эффективная производительность', from: '240 pallet/day', to: '300 pallet/day' },
  ]);
});

test('model picker shows each active calculation position once', () => {
  const position = { position_id: 'p1', calculation_ready: true, calculation_profile: 'TRANSPORT_CYCLE_V1' };
  assert.deepEqual(brainCandidates([position, { ...position }, { ...position, position_id: 'p2', calculation_ready: false }], 'TRANSPORT_CYCLE'), [position]);
});
