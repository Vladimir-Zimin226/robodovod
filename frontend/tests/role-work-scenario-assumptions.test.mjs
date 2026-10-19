import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createTypicalObjectDraft, loadConfirmedTypicalObjectDraft, serializeDraft } from '../src/processRoleIntakeV2.js';
import { ROLE_WORK_SCENARIOS, applyRoleWorkScenario } from '../src/roleWorkScenarioAssumptions.js';
import { buildRoleWorkProfiles } from '../src/roleWorkProfiles.js';

test('review table agrees with the scenario values used by the browser', async () => {
  const csv = await readFile(new URL('../../data/role-work/role-process-measurement-template-v1.csv', import.meta.url), 'utf8');
  const [header, ...rows] = csv.trim().split(/\r?\n/).map((line) => line.split(';'));
  const records = rows.map((cells) => Object.fromEntries(header.map((name, index) => [name, cells[index]])));
  assert.equal(records.length, 4);
  for (const row of records) {
    assert.equal(row.work_data_source, 'ASSUMPTION');
    assert.equal(row.measurement_date, '');
    assert.equal(row.confirmed, 'true');
    assert.equal(Number(row.robotizable_task_minutes_per_person_shift) / Number(row.paid_process_minutes_per_person_shift), Number(row.robotizable_fraction));
    const scenario = ROLE_WORK_SCENARIOS[row.process_code]?.[row.role_code];
    assert.ok(scenario, `${row.process_code}/${row.role_code}`);
    assert.equal(row.evidence_ref, scenario.id);
    assert.equal(row.object_role_headcount, scenario.headcount);
    assert.equal(row.monthly_amount_rub_per_person, scenario.monthlyEmployerCost);
    assert.equal(row.manual_units_per_person_shift, scenario.manualUnitsPerShift);
    assert.equal(row.robotizable_fraction, scenario.robotizableFraction);
  }
});

test('typical warehouse includes a paid loader and both role effects can be serialized', () => {
  const draft = loadConfirmedTypicalObjectDraft('retail');
  assert.equal(draft.roles.length, 2);
  assert.deepEqual(draft.roles.map((role) => role.roleCode), ['forklift_driver', 'loader']);
  assert.equal(draft.roles[1].salary, '104160');
  const raw = serializeDraft(draft);
  assert.equal(raw.roles[1].monthly_gross_salary.provenance.source, 'ASSUMPTION');
  const roleRefs = draft.roles.map((role) => role.roleId);
  const capacityRequest = { process: { process_code: 'warehouse_receiving_shipping', role_refs: roleRefs },
    role_pool: { roles: draft.roles.map((role) => ({ role_id: role.roleId, role_code: role.roleCode,
      headcount: { normalized_value: role.headcount } })) } };
  const values = applyRoleWorkScenario({ sources: {}, assumptions: {}, roleWorkProfiles: {} }, capacityRequest);
  assert.equal(values.primaryRoleId, roleRefs[0]);
  assert.equal(values.manualUnitsPerShift, '100');
  assert.equal(values.robotizableShare, '0.8');
  assert.equal(values.assumptions.manual_units_per_shift.confirmed, true);
  const profiles = buildRoleWorkProfiles(values, roleRefs, values.primaryRoleId);
  assert.equal(profiles[0].robotizable_fraction, '0.8');
  assert.equal(profiles[1].robotizable_fraction, '0.25');
  assert.equal(profiles[1].manual_units_per_shift, '250');
  assert.ok(profiles.every((profile) => profile.source === 'ASSUMPTION' && profile.confirmed));
  const changed = structuredClone(capacityRequest);
  changed.role_pool.roles[1].headcount.normalized_value = '9';
  assert.equal(applyRoleWorkScenario({ marker: true }, changed).marker, true);
  assert.equal(applyRoleWorkScenario({ marker: true }, changed).primaryRoleId, undefined);
});

test('airport and clinic typical objects use documented role assumptions', () => {
  for (const [objectType, code, roleCode] of [
    ['airport', 'airport_terminal_cleaning', 'terminal_cleaner'],
    ['clinic', 'clinic_food', 'catering_worker'],
  ]) {
    const draft = createTypicalObjectDraft(objectType);
    const role = draft.roles[0];
    const row = ROLE_WORK_SCENARIOS[code][roleCode];
    assert.equal(role.headcount, row.headcount);
    assert.equal(role.salary, row.monthlyEmployerCost);
    const values = applyRoleWorkScenario({ sources: {}, assumptions: {}, roleWorkProfiles: {} }, {
      process: { process_code: code, role_refs: [role.roleId] },
      role_pool: { roles: [{ role_id: role.roleId, role_code: role.roleCode,
        headcount: { normalized_value: role.headcount } }] },
    });
    assert.equal(values.manualUnitsPerShift, row.manualUnitsPerShift);
    assert.equal(values.robotizableShare, row.robotizableFraction);
  }
});
