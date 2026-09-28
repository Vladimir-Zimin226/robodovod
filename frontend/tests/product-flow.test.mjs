import test from 'node:test';
import assert from 'node:assert/strict';
import { createTypicalObjectDraft, loadConfirmedTypicalObjectDraft, createDraft, validateDraft, serializeDraft, confirmProcessAssumption, confirmFacilityArea, confirmRoleAssumption, updateProcess } from '../src/processRoleIntakeV2.js';
import { applyTypicalObjectEconomics } from '../src/economicsDemoAssumptions.js';
import { valuesAtDepth } from '../src/economicsDepth.js';
import { buildPartialEconomicsRunRequest } from '../src/economicsInputV2.js';
import { demoCandidates } from '../src/demoCapacityFlow.js';

const fields = [
  ['Труд', 'manualUnitsPerShift', 'manual_units_per_shift'],
  ['Труд', 'controlHeadcount', 'control_headcount'],
  ['Покупка', 'horizonYears', 'horizon_years'],
  ['Покупка', 'discountRate', 'discount_rate'],
  ['Покупка', 'implementationCost', 'implementation_cost_total_gross'],
  ['RaaS', 'raasMonthly', 'raas_monthly_per_robot_gross'],
  ['RaaS', 'raasContractMonths', 'raas_contract_months'],
  ['Визуализация', 'startSeconds', 'start_seconds_from_midnight'],
];
const values = { capacityRunId: 'capacity.test', sources: {}, assumptions: {}, userValues: {},
  timezone: 'Asia/Sakhalin', startSeconds: '32400' };

test('one typical-loader action confirms all three objects and preserves assumption provenance', () => {
  for (const type of ['retail', 'airport', 'clinic']) {
    const draft = loadConfirmedTypicalObjectDraft(type);
    assert.deepEqual(validateDraft(draft, { requireFacilityAreas: true }).filter((item) => item.severity === 'BLOCKER'), []);
    assert.ok(draft.roles.every((role) => role.salaryConfirmed));
    const process = draft.processes.find((item) => item.active);
    for (const [key, source] of Object.entries(process.fieldSources)) {
      if (source === 'ASSUMPTION' && process[key]) assert.equal(process.fieldConfirmations[key], true);
    }
    const serialized = serializeDraft(draft);
    assert.equal(serialized.facility_areas.total_area.provenance.source, 'ASSUMPTION');
    assert.equal(serialized.facility_areas.total_area.provenance.user_confirmed, true);
    if (process.batch) {
      const edited = updateProcess(draft, process.processId, { batch: '2' });
      assert.equal(edited.processes.find((p) => p.active).fieldConfirmations.batch, false);
    }
  }
});

test('missing facility areas block the actual intake before normalization', () => {
  assert.deepEqual(validateDraft(createDraft('clinic'), { requireFacilityAreas: true })
    .filter((item) => item.code === 'AREA_REQUIRED').map((item) => item.ref), ['facility.totalArea', 'facility.activeArea']);
  for (const type of ['retail', 'airport', 'clinic']) {
    const draft = createTypicalObjectDraft(type);
    assert.equal(validateDraft(draft, { requireFacilityAreas: true }).some((item) => item.code === 'AREA_REQUIRED'), false);
    assert.equal(draft.processes.filter((item) => item.active).length, 1);
  }
});

test('clinic preliminary delivery accepts generic transport and delivery profiles, with typed units handled by C11', () => {
  const transport = { position_id: 'transport', calculation_ready: true, calculation_profile: 'TRANSPORT_CYCLE_V1' };
  const delivery = { position_id: 'delivery', calculation_ready: true, calculation_profile: 'DELIVERY_CYCLE_V1' };
  assert.deepEqual(demoCandidates([transport, delivery], 'DELIVERY_CYCLE'), [transport, delivery]);
  assert.deepEqual(demoCandidates([transport, delivery], 'TRANSPORT_CYCLE'), [transport]);
});

test('preliminary delivery never includes excluded, research or unsupported models', () => {
  const eligible = { position_id: 'delivery', calculation_ready: true, calculation_profile: 'TRANSPORT_CYCLE_V1' };
  const rows = [eligible, { ...eligible, position_id: 'excluded', selection: { status: 'EXCLUDED' } },
    { ...eligible, position_id: 'research', maturity_status: 'RND' },
    { ...eligible, position_id: 'missing', calculation_ready: false },
    { ...eligible, position_id: 'cleaner', calculation_profile: 'CLEANING_AREA_V1' }];
  assert.deepEqual(demoCandidates(rows, 'DELIVERY_CYCLE'), [eligible]);
});

test('airport and clinic preserve organizer scope and distinguish assumed staff allocations', () => {
  const airport = createTypicalObjectDraft('airport');
  assert.equal(airport.facility.totalArea, '85000');
  assert.equal(airport.processes.find((item) => item.active).demand, '51000');
  const clinic = createTypicalObjectDraft('clinic');
  const food = clinic.processes.find((item) => item.active);
  assert.equal(food.demand, '1950'); assert.equal(food.distance, '180');
  assert.equal(food.fieldSources.batch, 'ASSUMPTION');
  assert.equal(food.fieldConfirmations.batch, false);
  assert.equal(clinic.roles[0].headcount, '6');
  assert.equal(clinic.roles[0].headcountSource, 'ASSUMPTION');
  assert.equal(clinic.roles[0].salary, '52000');
});

test('organizer proposals serialize through the existing provenance contract with their source retained', () => {
  for (const type of ['retail', 'airport', 'clinic']) {
    let draft = createTypicalObjectDraft(type);
    const process = draft.processes.find((item) => item.active);
    if (process.batch) draft = confirmProcessAssumption(draft, process.processId, 'batch');
    for (const key of ['totalArea', 'activeArea']) draft = confirmFacilityArea(draft, key);
    for (const role of draft.roles) if (role.salarySource === 'ASSUMPTION') draft = confirmRoleAssumption(draft, role.roleId);
    const raw = serializeDraft(draft);
    assert.equal(raw.facility_areas.total_area.provenance.source, 'ASSUMPTION');
    assert.match(raw.facility_areas.total_area.provenance.raw_text, /object_profiles.json/);
    assert.equal(raw.facility_areas.total_area.provenance.user_confirmed, true);
    assert.equal(raw.object_kind, draft.objectKind);
  }
});

test('typical economics fills, confirms and persists sources without warehouse attribution on other objects', () => {
  for (const kind of ['WAREHOUSE', 'AIRPORT', 'CLINIC']) {
    const next = applyTypicalObjectEconomics(values, fields, kind, { status: 'ESTIMATE', value: '83.5', formula: 'F08', source_refs: ['R03'] });
    assert.equal(next.calculationDepth, 'FULL');
    assert.equal(next.manualUnitsPerShift, '83.5');
    assert.equal(next.timezone, 'Asia/Sakhalin');
    assert.equal(next.startSeconds, '32400');
    assert.equal(next.grossConfirm, true); assert.equal(next.raasScopeConfirm, true);
    const body = buildPartialEconomicsRunRequest({ values: next, capacityRequest: { input_revision: 'revision', process: { role_refs: ['role'] } },
      project: { id: 'project' }, scenario: { id: 'base' } });
    assert.equal(body.input.calculation_depth, 'FULL');
    assert.equal(body.input.assumption_evidence.manual_units_per_shift.confirmed, true);
    assert.equal(body.input.assumption_evidence.start_seconds_from_midnight.confirmed_value, '32400');
    assert.equal(body.input.assumption_evidence.start_seconds_from_midnight.confirmed, true);
    assert.equal(body.input.assumption_evidence.purchase_price_override_gross.confirmed, true);
    if (kind !== 'WAREHOUSE') {
      assert.equal(body.input.assumption_evidence.implementation_cost_total_gross.template_id, null);
      assert.equal(body.input.assumption_evidence.implementation_cost_total_gross.source, 'USER');
      assert.equal(next.raasContractMonths, '84');
    }
  }
  assert.deepEqual(values.assumptions, {});
});

test('saving a lower depth omits hidden higher inputs and keeps the editor values', () => {
  const full = applyTypicalObjectEconomics(values, fields, 'CLINIC');
  const basic = valuesAtDepth({ ...full, calculationDepth: 'BASIC' }, fields);
  assert.equal(basic.horizonYears, ''); assert.equal(basic.raasMonthly, '');
  assert.equal(basic.technicianRaasMode, '');
  assert.equal(basic.assumptions.horizon_years, undefined);
  assert.equal(full.horizonYears, '7');
  const advanced = valuesAtDepth({ ...full, calculationDepth: 'ADVANCED' }, fields);
  assert.equal(advanced.horizonYears, '7'); assert.equal(advanced.raasMonthly, '');
});
