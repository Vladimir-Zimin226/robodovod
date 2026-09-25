import test from 'node:test';
import assert from 'node:assert/strict';
import { canImportProfile, confirmField, editProfile, emptyProfile, mergeAssistantDraft,
  profileReadiness, readGuestProfile, SESSION_TTL_MS, toV2Draft, writeGuestProfile } from '../src/assistantInterview.js';
import { serializeDraft } from '../src/processRoleIntakeV2.js';

const confirmed = (key, value, profile) => confirmField(editProfile(profile, key, value), key, true);

function warehouseProfile() {
  let profile = emptyProfile();
  for (const [key, value] of Object.entries({
    object_type: 'retail', process_type: 'transport', cargo_type: 'pallets',
    operations_per_day: '800', shifts_count: '2', shift_hours: '11', operating_days: '250',
    avg_distance_m: '180', units_per_trip: '1', zone_label: 'Отгрузка', zone_constraints: 'Узкий проход',
    staff_headcount: '12', monthly_gross_salary: '120000',
  })) profile = confirmed(key, value, profile);
  return profile;
}

test('interview proposals stay unconfirmed and conflicting text never overwrites a value', () => {
  let profile = emptyProfile();
  const first = mergeAssistantDraft(profile, { fields: { process_type: 'transport', cargo_type: 'pallets', pallets_per_day: 800 }, summary: '800 паллет в сутки' });
  profile = first.profile;
  assert.equal(profile.fields.object_type.value, 'retail');
  assert.equal(profile.fields.operations_per_day.source, 'USER_STATEMENT');
  assert.equal(profile.fields.operations_per_day.confirmed, false);
  assert.equal(canImportProfile(profile), false);
  profile = confirmed('operations_per_day', '600', profile);
  const second = mergeAssistantDraft(profile, { fields: { pallets_per_day: 900 }, summary: '900 паллет в сутки' });
  assert.deepEqual(second.conflicts, ['operations_per_day']);
  assert.equal(second.profile.fields.operations_per_day.value, '600');
  assert.equal(second.profile.fields.operations_per_day.confirmed, true);
});

test('confirmed warehouse interview transfers numbers, source and zone into v2 without running calculation', () => {
  const profile = warehouseProfile();
  assert.equal(profileReadiness(profile).capacity.length, 0);
  assert.equal(canImportProfile(profile), true);
  const draft = toV2Draft(profile);
  const request = serializeDraft(draft);
  const process = request.processes.find((item) => item.active);
  assert.equal(process.process_code, 'warehouse_receiving_shipping');
  assert.equal(process.demand.value, '800');
  assert.equal(process.demand.provenance.source, 'USER');
  assert.equal(process.route_distance.value, '180');
  assert.equal(process.explicit_batch.value, '1');
  assert.equal(draft.zones[0].label, 'Отгрузка');
  assert.equal(draft.zones[0].constraints, 'Узкий проход');
  assert.equal(request.roles[0].monthly_gross_salary.value, '120000');
  assert.equal(request.roles[0].monthly_gross_salary.provenance.user_confirmed, true);
  assert.equal('model_id' in request, false);
  assert.equal('run_id' in request, false);
});

test('220 pallets and 120 m require an explicit confirmed trip quantity', () => {
  let profile = warehouseProfile();
  profile = confirmed('operations_per_day', '220', profile);
  profile = confirmed('avg_distance_m', '120', profile);
  profile = editProfile(profile, 'units_per_trip', '');
  assert.equal(canImportProfile(profile), false);
  assert.ok(profileReadiness(profile).capacity.includes('units_per_trip'));
  profile = confirmed('units_per_trip', '1', profile);
  const process = serializeDraft(toV2Draft(profile)).processes.find((item) => item.active);
  assert.equal(process.demand.value, '220');
  assert.equal(process.route_distance.value, '120');
  assert.equal(process.explicit_batch.value, '1');
  assert.equal(process.explicit_batch.provenance.source, 'USER');
});

test('missing or disputed data cannot be imported and unknown economy remains explicit', () => {
  const profile = warehouseProfile();
  const changed = editProfile(profile, 'avg_distance_m', '200');
  assert.equal(canImportProfile(changed), false);
  assert.ok(profileReadiness(changed).capacity.includes('avg_distance_m'));
  assert.match(profileReadiness(changed).economics[0], /закупочные/);
  assert.equal(canImportProfile(confirmed('peak_multiplier', '0', profile)), false);
});

test('guest profile expires after eight hours in session storage', () => {
  const data = new Map();
  const storage = { getItem: (key) => data.get(key), setItem: (key, value) => data.set(key, value) };
  const profile = warehouseProfile();
  writeGuestProfile(storage, profile, 1000);
  assert.deepEqual(readGuestProfile(storage, 1000 + SESSION_TTL_MS - 1), profile);
  assert.deepEqual(readGuestProfile(storage, 1000 + SESSION_TTL_MS), emptyProfile());
});
