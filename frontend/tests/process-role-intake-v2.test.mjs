import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  addZone,
  PROCESS_DEFINITIONS,
  confirmRoleAssumption,
  confirmProcessAssumption,
  createDraft,
  createWarehouseDemoDraft,
  createWarehouseFileDraft,
  createNormalizationClient,
  definitionsFor,
  removeZone,
  serializeDraft,
  setRoleActive,
  updateProcess,
  updateRole,
  updateZone,
  validateDraft,
  zoneForProcessId,
} from '../src/processRoleIntakeV2.js';

test('warehouse file feeds v2 with FILE provenance and never converts legacy FTE cost to gross salary', () => {
  const sha = 'a'.repeat(64);
  const draft = createWarehouseFileDraft({ object_type: 'retail', process_type: 'transport', pallets_per_day: 2000,
    shifts_count: 2, shift_hours: 11, operating_days: 365, avg_distance_m: 120,
    staff_headcount: 25, fte_cost_rub: 1562400 },
  { parameter_provenance: { volume: { source: { name: 'warehouse.csv', sha256: sha } } } });
  const process = draft.processes.find((item) => item.code === 'warehouse_receiving_shipping');
  assert.equal(process.batch, '');
  assert.ok(validateDraft(draft).some((issue) => issue.code === 'BATCH_REQUIRED'));
  const request = serializeDraft(updateProcess(draft, process.processId, { batch: '1' }));
  assert.equal(request.processes.find((item) => item.active).demand.provenance.source, 'FILE');
  assert.equal(request.processes.find((item) => item.active).demand.provenance.file_sha256, sha);
  assert.equal(request.roles[0].headcount.provenance.file_sha256, sha);
  assert.equal(request.roles[0].monthly_gross_salary, null);
  assert.equal('fte_cost_rub' in request, false);
});

test('demo pallet per trip remains an assumption until explicitly confirmed', () => {
  let draft = createWarehouseDemoDraft();
  const process = draft.processes.find((item) => item.active);
  assert.equal(process.batch, '1');
  assert.ok(validateDraft(draft).some((issue) => issue.code === 'BATCH_CONFIRMATION_REQUIRED'));
  draft = confirmProcessAssumption(draft, process.processId, 'batch');
  assert.equal(validateDraft(draft).some((issue) => issue.code === 'BATCH_CONFIRMATION_REQUIRED'), false);
  // The salary is a separate demo assumption; this test only checks batch provenance.
  const updated = draft.processes.find((item) => item.active);
  assert.equal(updated.fieldConfirmations.batch, true);
  draft = updateProcess(draft, process.processId, { batch: '2' });
  assert.equal(draft.processes.find((item) => item.active).fieldConfirmations.batch, false);
});

function validWarehouseDraft() {
  let draft = createDraft('retail');
  const code = 'warehouse_receiving_shipping';
  draft = updateProcess(draft, code, {
    active: true, demand: '2000', shifts: '2', hours: '11', days: '365', distance: '120', batch: '1',
  });
  return draft;
}

test('v2 projection keeps all 28 K19 blocks and object boundaries', () => {
  assert.equal(PROCESS_DEFINITIONS.length, 28);
  assert.equal(definitionsFor('retail').length, 6);
  assert.equal(definitionsFor('airport').length, 10);
  assert.equal(definitionsFor('clinic').length, 12);
  assert.equal(PROCESS_DEFINITIONS.find((item) => item.code === 'airport_catering').roles[0], 'trolley_operator');
  assert.equal(PROCESS_DEFINITIONS.find((item) => item.code === 'clinic_food').quantityKind, 'PORTION');
});

test('every suggested role can be activated and remains process-scoped', () => {
  for (const definition of PROCESS_DEFINITIONS) {
    for (const roleCode of definition.roles) {
      const objectType = { WAREHOUSE: 'retail', AIRPORT: 'airport', CLINIC: 'clinic' }[definition.objectKind];
      let draft = createDraft(objectType);
      draft = setRoleActive(draft, definition.code, roleCode, true);
      assert.equal(draft.roles.length, 1);
      assert.equal(draft.roles[0].roleCode, roleCode);
      assert.deepEqual(draft.roles[0].processIds, [`${draft.zones[0].zoneId}.${definition.code}`]);
    }
  }
});

test('zones keep separate process inputs and stable C11/C23 identities', () => {
  let draft = validWarehouseDraft();
  draft = addZone(draft, 'retail');
  const first = draft.processes.find((item) => item.zoneId === draft.zones[0].zoneId && item.code === 'warehouse_receiving_shipping');
  const second = draft.processes.find((item) => item.zoneId === draft.zones[1].zoneId && item.code === 'warehouse_receiving_shipping');
  draft = updateZone(draft, second.zoneId, { label: 'Отгрузка', constraints: 'Узкий проход' });
  draft = updateProcess(draft, second.processId, { active: true, demand: '600', shifts: '2', hours: '8', days: '250', distance: '80', batch: '1' });
  assert.equal(draft.processes.find((item) => item.processId === first.processId).demand, '2000');
  assert.equal(draft.processes.find((item) => item.processId === second.processId).demand, '600');
  assert.equal(zoneForProcessId(second.processId), second.zoneId);
  assert.equal(draft.zones[1].constraints, 'Узкий проход');
  const request = serializeDraft(draft);
  assert.equal(request.processes.find((item) => item.process_id === second.processId).route_distance.value, '80');
  assert.equal(new Set(request.processes.map((item) => item.process_id)).size, request.processes.length);
  const removed = removeZone(draft, second.zoneId);
  assert.equal(removed.zones.length, 1);
  assert.equal(removed.processes.length, definitionsFor('retail').length);
  const addedAgain = addZone(removed, 'retail');
  assert.notEqual(addedAgain.zones[1].zoneId, second.zoneId);
});

test('empty inactive blocks serialize without hidden normalized quantities', () => {
  const request = serializeDraft(createDraft('clinic'));
  assert.equal(request.schema_version, 'calculation-intake-v2');
  assert.equal(request.processes.length, 12);
  assert.ok(request.processes.every((item) => item.active === false && item.demand === null));
  assert.equal(JSON.stringify(request).includes('normalized_value'), false);
  assert.equal(JSON.stringify(request).includes('fte_cost_rub'), false);
});

test('salary stays monthly gross raw input and missing salary is explicit', () => {
  let draft = validWarehouseDraft();
  draft = setRoleActive(draft, 'warehouse_receiving_shipping', 'forklift_driver', true);
  const roleId = draft.roles[0].roleId;
  draft = updateRole(draft, roleId, { headcount: '25' });
  assert.ok(validateDraft(draft).some((item) => item.code === 'SALARY_REQUIRED'));
  draft = updateRole(draft, roleId, { salary: '120000' });
  const request = serializeDraft(draft);
  assert.equal(request.roles[0].monthly_gross_salary.value, '120000');
  assert.equal(request.roles[0].monthly_gross_salary.unit, 'RUB/person/month');
  assert.equal(JSON.stringify(request).includes('15.624'), false);
});

test('explicit zero salary carries the required zero-cost marker', () => {
  let draft = validWarehouseDraft();
  draft = setRoleActive(draft, 'warehouse_receiving_shipping', 'forklift_driver', true);
  const roleId = draft.roles[0].roleId;
  draft = updateRole(draft, roleId, { headcount: '1', salary: '0' });
  assert.equal(validateDraft(draft).some((item) => item.code === 'SALARY_REQUIRED'), false);
  assert.equal(serializeDraft(draft).roles[0].zero_cost_marker, 'ZERO_COST_ROLE');
  draft = updateRole(draft, roleId, { salary: '0.00' });
  assert.equal(serializeDraft(draft).roles[0].zero_cost_marker, 'ZERO_COST_ROLE');
});

test('assumption confirmation creates a revision-bound override event', () => {
  let draft = validWarehouseDraft();
  draft = setRoleActive(draft, 'warehouse_receiving_shipping', 'forklift_driver', true);
  const roleId = draft.roles[0].roleId;
  draft = updateRole(draft, roleId, { headcount: '25', salary: '120000', salarySource: 'ASSUMPTION', salaryConfirmed: false });
  assert.ok(validateDraft(draft).some((item) => item.code === 'ASSUMPTION_CONFIRMATION_REQUIRED'));
  const previousRevision = draft.inputRevision;
  draft = confirmRoleAssumption(draft, roleId);
  assert.notEqual(draft.inputRevision, previousRevision);
  assert.equal(draft.overrideEvents.at(-1).inputRevision, draft.inputRevision);
  assert.equal(serializeDraft(draft).roles[0].monthly_gross_salary.provenance.user_confirmed, true);
});

test('no-role process reports no FOT benefit without blocking technical intake', () => {
  let draft = createDraft('clinic');
  draft = updateProcess(draft, 'clinic_safety_requirements', { active: true, demand: '1', shifts: '1', hours: '8', days: '365' });
  const issues = validateDraft(draft);
  assert.ok(issues.some((item) => item.code === 'NO_FOT_BENEFIT'));
  assert.equal(issues.some((item) => item.severity === 'BLOCKER'), false);
});

test('schedule validation rejects H over 24 rather than clamping it', () => {
  let draft = validWarehouseDraft();
  draft = updateProcess(draft, 'warehouse_receiving_shipping', { shifts: '3', hours: '12' });
  assert.ok(validateDraft(draft).some((item) => item.code === 'SCHEDULE_OVER_24H'));
  assert.throws(() => serializeDraft(draft), /INTAKE_DRAFT_INVALID/);
});

test('normalization client sends the C03 contract and rejects stale responses', async () => {
  const pending = [];
  const fetchMock = (url, options) => new Promise((resolve) => pending.push({ url, options, resolve }));
  const client = createNormalizationClient(fetchMock);
  const firstDraft = validWarehouseDraft();
  const secondDraft = updateProcess(firstDraft, 'warehouse_receiving_shipping', { demand: '2100' });
  const first = client(firstDraft);
  const second = client(secondDraft);
  assert.equal(pending[0].url, '/api/v2/calculation-intake/normalize');
  const firstRequest = JSON.parse(pending[0].options.body);
  assert.equal(firstRequest.input_revision, firstDraft.inputRevision);
  pending[0].resolve({ ok: true, json: async () => ({ schema_version: 'calculation-intake-normalization-v2', input_revision: firstDraft.inputRevision }) });
  await assert.rejects(first, /STALE_INTAKE_RESPONSE/);
  pending[1].resolve({ ok: true, json: async () => ({ schema_version: 'calculation-intake-normalization-v2', input_revision: secondDraft.inputRevision }) });
  const current = await second;
  assert.equal(current.response.input_revision, secondDraft.inputRevision);
});

test('normalization response is stale when the draft changed without another request', async () => {
  let resolveResponse;
  let latestRevision;
  const client = createNormalizationClient(
    () => new Promise((resolve) => { resolveResponse = resolve; }),
    '/api/v2/calculation-intake/normalize',
    () => latestRevision,
  );
  const draft = validWarehouseDraft();
  latestRevision = draft.inputRevision;
  const pending = client(draft);
  latestRevision = 'draft.changed';
  resolveResponse({ ok: true, json: async () => ({ schema_version: 'calculation-intake-normalization-v2', input_revision: draft.inputRevision }) });
  await assert.rejects(pending, /STALE_INTAKE_RESPONSE/);
});

test('C03 golden fixture keeps raw and normalized units visible to presentation', async () => {
  const fixture = JSON.parse(await readFile(new URL('../../contracts/fixtures/calculation-intake-v2.clinic.json', import.meta.url), 'utf8'));
  const demand = fixture.response.conversions.find((item) => item.field.endsWith('.demand'));
  assert.equal(demand.raw_unit, 'portion/day');
  assert.equal(demand.normalized_unit, 'portion/day');
  assert.equal(fixture.response.schema_version, 'calculation-intake-normalization-v2');
});

test('component exposes keyboard-native controls and server trace labels', async () => {
  const source = await readFile(new URL('../src/components/ProcessRoleIntakeV2.jsx', import.meta.url), 'utf8');
  assert.match(source, /aria-label="Процессы и роли v2"/);
  assert.match(source, /aria-expanded=/);
  assert.match(source, /aria-live="polite"/);
  assert.match(source, /type="checkbox"/);
  assert.match(source, /raw \{node\.raw_value\}.*normalized \{node\.normalized_value\}/s);
  assert.doesNotMatch(source, /15\.624/);
});
