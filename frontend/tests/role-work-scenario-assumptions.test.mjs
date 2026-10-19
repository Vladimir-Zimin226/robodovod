import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PROCESS_DEFINITIONS, applyScenarioRolesToDraft, createDraft, createTypicalObjectDraft,
  loadConfirmedTypicalObjectDraft, serializeDraft, setRoleActive, updateProcess, updateRole } from '../src/processRoleIntakeV2.js';
import { ROLE_WORK_SCENARIO_ROWS, ROLE_WORK_SCENARIOS, applyRoleWorkScenario } from '../src/roleWorkScenarioAssumptions.js';
import { buildRoleWorkProfiles } from '../src/roleWorkProfiles.js';

test('review table agrees with the scenario values used by the browser', async () => {
  const csv = await readFile(new URL('../../data/role-work/role-process-measurement-template-v1.csv', import.meta.url), 'utf8');
  const [header, ...rows] = csv.trim().split(/\r?\n/).map((line) => line.split(';'));
  const records = rows.map((cells) => Object.fromEntries(header.map((name, index) => [name, cells[index]])));
  assert.equal(records.length, 35);
  assert.deepEqual(records, ROLE_WORK_SCENARIO_ROWS);
  const defined = PROCESS_DEFINITIONS.flatMap((process) => process.roles.map((role) => `${process.code}/${role}`));
  assert.deepEqual(records.map((row) => `${row.process_code}/${row.role_code}`).sort(), defined.sort());
  for (const row of records) {
    assert.equal(row.work_data_source, 'ASSUMPTION');
    assert.equal(row.measurement_date, '');
    assert.equal(row.confirmed, String(row.calculation_status === 'CALCULABLE'));
    assert.equal(Number(row.robotizable_task_minutes_per_person_shift) / Number(row.paid_process_minutes_per_person_shift), Number(row.robotizable_fraction));
    const scenario = ROLE_WORK_SCENARIOS[row.process_code]?.[row.role_code];
    if (row.calculation_status !== 'CALCULABLE') {
      assert.equal(scenario, undefined);
      continue;
    }
    assert.ok(scenario, `${row.process_code}/${row.role_code}`);
    assert.equal(row.evidence_ref, scenario.id);
    assert.equal(Number(row.object_role_headcount) * Number(row.process_allocation_fraction), Number(scenario.headcount));
    assert.equal(row.monthly_amount_rub_per_person, scenario.monthlyEmployerCost);
    assert.equal(row.manual_units_per_person_shift, scenario.manualUnitsPerShift);
    assert.equal(row.robotizable_fraction, scenario.robotizableFraction);
  }
});

test('shared staff allocations close without reusing a person twice', () => {
  for (const [objectKind, roleCode, count] of [
    ['AIRPORT', 'trolley_operator', 3], ['CLINIC', 'sanitary', 3], ['CLINIC', 'porter', 3],
  ]) {
    const rows = ROLE_WORK_SCENARIO_ROWS.filter((row) => row.object_kind === objectKind && row.role_code === roleCode);
    assert.equal(rows.length, count);
    assert.ok(Math.abs(rows.reduce((sum, row) => sum + Number(row.process_allocation_fraction), 0) - 1) < 1e-12);
  }
  assert.equal(ROLE_WORK_SCENARIO_ROWS.filter((row) => row.calculation_status === 'CALCULABLE').length, 13);
  assert.equal(ROLE_WORK_SCENARIO_ROWS.filter((row) => row.calculation_status === 'ALLOCATION_REQUIRED').length, 7);
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
  const reversed = structuredClone(capacityRequest);
  reversed.process.role_refs.reverse();
  assert.equal(applyRoleWorkScenario({ sources: {}, assumptions: {}, roleWorkProfiles: {} }, reversed).primaryRoleId, roleRefs[0]);
  const changed = structuredClone(capacityRequest);
  changed.role_pool.roles[1].headcount.normalized_value = '9';
  assert.equal(applyRoleWorkScenario({ marker: true }, changed).marker, true);
  assert.equal(applyRoleWorkScenario({ marker: true }, changed).primaryRoleId, undefined);
  changed.role_pool.roles[1].headcount.normalized_value = '8';
  changed.role_pool.roles[1].process_ids = ['receiving', 'other-process'];
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

test('other supported profiles fill empty work fields without replacing site data', () => {
  let draft = createDraft('clinic');
  draft = updateProcess(draft, 'clinic_linen', { active: true });
  const filled = applyScenarioRolesToDraft(draft, 'clinic_linen');
  assert.equal(filled.roles.length, 1);
  assert.equal(filled.roles[0].headcount, '18');
  assert.equal(filled.roles[0].salary, '65100');
  assert.equal(filled.roles[0].salarySource, 'ASSUMPTION');
  assert.equal(filled.roles[0].salaryConfirmed, true);
  const user = updateRole(filled, filled.roles[0].roleId, {
    headcount: '19', headcountSource: 'USER', salary: '70000', salarySource: 'USER' });
  assert.deepEqual(applyScenarioRolesToDraft(user, 'clinic_linen').roles, user.roles);
  let shared = updateProcess(createDraft('clinic'), 'clinic_medicines', { active: true });
  shared = setRoleActive(shared, 'clinic_medicines', 'sanitary', true);
  assert.equal(applyScenarioRolesToDraft(shared, 'clinic_medicines'), shared);
});
