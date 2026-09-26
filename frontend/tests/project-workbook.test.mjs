import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { workbookDraft, confirmWorkbookDraft, workbookEconomics } from '../src/projectWorkbook.js';
import { createDraft, updateProcess, setRoleActive, updateRole, serializeDraft, validateDraft } from '../src/processRoleIntakeV2.js';

const fixtures = JSON.parse(readFileSync(new URL('../../docs/planning/assets/f2/normalized-examples.json', import.meta.url), 'utf8'));
for (const [name, input] of Object.entries(fixtures)) {
  test(`${name}: import confirmation and manual inputs retain equal physical/labour values`, () => {
    const proposal = workbookDraft(input);
    assert.ok(validateDraft(proposal).some((issue) => issue.code === 'IMPORT_CONFIRMATION_REQUIRED'));
    assert.throws(() => serializeDraft(proposal));
    const imported = serializeDraft(confirmWorkbookDraft(proposal));
    const source = input.records['Процессы'].operation;
    let manual = createDraft('retail');
    manual = updateProcess(manual, 'warehouse_receiving_shipping', { active: true,
      demand: source.demand.value, shifts: source.shifts.value, hours: source.hours.value, days: source.days.value,
      distance: source.distance.value, batch: source.batch.value });
    manual = setRoleActive(manual, 'warehouse_receiving_shipping', 'forklift_driver', true);
    manual = updateRole(manual, 'draft.warehouse.forklift_driver', { headcount: input.records['Роли'].staff.headcount.value, salary: input.records['Роли'].staff.salary.value });
    const hand = serializeDraft(manual);
    const numeric = (process) => [process.demand.value, process.schedule.shifts_per_day.value, process.schedule.shift_hours.value,
      process.schedule.days_per_year.value, process.route_distance.value, process.explicit_batch.value];
    assert.deepEqual(numeric(imported.processes[0]), numeric(hand.processes.find((p) => p.active)));
    assert.equal(imported.roles[0].monthly_gross_salary.value, hand.roles[0].monthly_gross_salary.value);
    assert.equal(imported.roles[0].monthly_gross_salary.unit, 'RUB/person/month');
    assert.match(proposal.zones[0].constraints, /800 кг/);
    assert.equal(proposal.processes[0].exchangeSeconds, '90');
    const economy = workbookEconomics(input);
    assert.equal(economy.raas_contract_months, '60');
    assert.equal(economy.role_salaries_confirmed_as_monthly_gross, undefined);
    assert.ok(Object.values(economy.assumption_evidence).every((item) => item.confirmed === false));
    assert.match(economy.assumption_evidence.horizon_years.rationale, /SHA256/);
  });
}

test('unknown values stay empty and multiple zones/processes preserve shared roles', () => {
  const input = structuredClone(fixtures['interview-220-120']);
  input.records['Процессы'].operation.demand.value = null;
  input.records['Зоны'].annex = structuredClone(input.records['Зоны'].main);
  input.records['Процессы'].annex = structuredClone(input.records['Процессы'].operation);
  input.records['Процессы'].annex.zone_id.value = 'annex';
  input.records['Роли'].staff.process_ids.value = 'operation,annex';
  const draft = workbookDraft(input);
  assert.equal(draft.zones.length, 2); assert.equal(draft.processes.length, 2); assert.equal(draft.roles.length, 1);
  assert.equal(draft.roles[0].processIds.length, 2); assert.equal(draft.processes[0].demand, '');
  assert.ok(validateDraft(confirmWorkbookDraft(draft)).some((issue) => issue.code === 'DEMAND_REQUIRED'));
  input.records['Объект'].main.timezone.value = null;
  input.records['Экономика'].main.start_seconds_from_midnight.value = null;
  const economy = workbookEconomics(input);
  assert.equal(economy.timezone, '');
  assert.equal(economy.start_seconds_from_midnight, '');
});

test('airport and clinic alternative flow units keep their quantity kind', () => {
  for (const [type, code, unit, kind, role] of [
    ['airport', 'airport_baggage', 'cart/day', 'CART', 'baggage_handler'],
    ['clinic', 'clinic_medicines', 'item/day', 'ITEM', 'sanitary'],
    ['clinic', 'clinic_results', 'item/day', 'DIGITAL_FLOW', 'lab_result_courier'],
  ]) {
    const input = structuredClone(fixtures['interview-220-120']);
    input.object_type = type;
    input.records['Процессы'].operation.process_code.value = code;
    input.records['Процессы'].operation.demand.unit = unit;
    input.records['Роли'].staff.role_code.value = role;
    const request = serializeDraft(confirmWorkbookDraft(workbookDraft(input)));
    assert.equal(request.processes[0].demand.unit, unit);
    assert.equal(request.processes[0].quantity_kind, kind);
    assert.equal(request.roles[0].role_code, role);
  }
});
