import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  PROCESS_DEFINITIONS,
  confirmRoleAssumption,
  createDraft,
  createNormalizationClient,
  definitionsFor,
  serializeDraft,
  setRoleActive,
  updateProcess,
  updateRole,
  validateDraft,
} from '../src/processRoleIntakeV2.js';

function validWarehouseDraft() {
  let draft = createDraft('retail');
  const code = 'warehouse_receiving_shipping';
  draft = updateProcess(draft, code, {
    active: true, demand: '2000', shifts: '2', hours: '11', days: '365', distance: '120',
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
      assert.deepEqual(draft.roles[0].processIds, [`${draft.objectId}.${definition.code}`]);
    }
  }
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
