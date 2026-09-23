import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  applyCommercialInputEdit,
  assertCommercialScenariosBundle,
  createCommercialSession,
  formatServerMetric,
  formatServerMoney,
  getCommercialScenariosModel,
  isCommercialScenariosBundle,
} from '../src/commercialScenariosModel.js';

const root = new URL('../..', import.meta.url);
const fixture = JSON.parse(await readFile(new URL('frontend/tests/fixtures/commercial-scenarios-v2.golden.json', root), 'utf8'));
const clone = () => structuredClone(fixture);

test('golden bundle exposes all six purchase/RaaS uncertainty combinations', () => {
  const model = getCommercialScenariosModel(fixture, 'revision.c21');
  assert.equal(model.scenarios.length, 6);
  assert.deepEqual(new Set(model.scenarios.map((item) => item.key)), new Set([
    'PURCHASE:PESSIMISTIC', 'PURCHASE:BASE', 'PURCHASE:OPTIMISTIC',
    'RAAS:PESSIMISTIC', 'RAAS:BASE', 'RAAS:OPTIMISTIC',
  ]));
  assert.equal(model.scenarios.find((item) => item.key === 'PURCHASE:BASE').recommendation.status, 'RECOMMENDED');
});

test('partial finance and unknown procurement never look ready or best', () => {
  const model = getCommercialScenariosModel(fixture);
  const partial = model.scenarios.find((item) => item.key === 'RAAS:PESSIMISTIC');
  assert.equal(partial.procurement.ready, false);
  assert.equal(partial.procurement.status, 'UNVERIFIED');
  assert.equal(partial.financial.status, 'INCOMPLETE');
  assert.equal(partial.financial.npvProject, 'Недостаточно данных');
  assert.equal(partial.recommendation.status, 'INCOMPLETE');
  assert.equal(partial.recommendation.candidate_id, null);
});

test('contract rejects a false server recommendation', () => {
  const raw = clone();
  const partial = raw.scenarios.find((item) => item.acquisition === 'RAAS' && item.uncertainty === 'PESSIMISTIC');
  partial.recommendation = { status: 'RECOMMENDED', candidate_id: 'candidate.false', reason_codes: [] };
  assert.throws(() => assertCommercialScenariosBundle(raw), /COMMERCIAL_FALSE_RECOMMENDATION/);
});

test('VAT remains explicitly unknown and frontend does not guess a rate', () => {
  const purchase = getCommercialScenariosModel(fixture).scenarios.find((item) => item.key === 'PURCHASE:BASE');
  assert.equal(purchase.procurement.taxBasis, 'CASH_GROSS_RUB');
  assert.equal(purchase.procurement.vatRate, null);
  assert.equal(purchase.procurement.cashGross, '3000000.00');
});

test('financial display consumes server metrics without deriving them from cashflows', () => {
  const raw = clone();
  const purchase = raw.scenarios.find((item) => item.acquisition === 'PURCHASE' && item.uncertainty === 'BASE');
  purchase.financial.npv_project.value = '123.45';
  purchase.financial.simple_payback = { status: 'NOT_REACHED', value: null, unit: 'YEAR' };
  const view = getCommercialScenariosModel(raw).scenarios.find((item) => item.key === 'PURCHASE:BASE');
  assert.equal(view.financial.npvProject, '123,45 ₽');
  assert.equal(view.financial.simplePayback, 'Не достигнута');
  assert.equal(view.financial.annualLedgers[0].delta, '0.00');
});

test('golden displayed money preserves exact server decimals', () => {
  assert.equal(formatServerMoney('3000000.00'), '3 000 000,00 ₽');
  assert.equal(formatServerMoney('-1500000.00'), '-1 500 000,00 ₽');
  assert.equal(formatServerMetric({ status: 'COMPLETE', value: '2.75', unit: 'YEAR' }), '2.75 YEAR');
});

test('user edit invalidates the old result instead of recalculating in browser', () => {
  const session = createCommercialSession(fixture);
  const edited = applyCommercialInputEdit(session, 'roleSalaries.role.operator', '110000');
  assert.equal(edited.inputs.roleSalaries['role.operator'], '110000');
  assert.equal(edited.result, null);
  assert.equal(edited.stale, true);
  assert.deepEqual(edited.dirtyFields, ['roleSalaries.role.operator']);
  assert.equal(session.result.scenarios.length, 6);
});

test('missing monthly gross salary remains visible and is not defaulted', () => {
  const model = getCommercialScenariosModel(fixture);
  const role = model.roles.find((item) => item.role_id === 'role.tech');
  assert.equal(role.monthly_gross_salary.status, 'MISSING');
  assert.equal(role.monthly_gross_salary.value, null);
  assert.equal(createCommercialSession(fixture).inputs.roleSalaries['role.tech'], '');
});

test('sensitivity uses six server deltas and keeps discrete-step reasons', () => {
  const variants = getCommercialScenariosModel(fixture).sensitivity;
  assert.equal(variants.length, 6);
  const volumeUp = variants.find((item) => item.parameter === 'OPERATION_VOLUME' && item.direction === 'UPPER');
  assert.equal(volumeUp.deltaNpv, '-1000000.00');
  assert.ok(volumeUp.reasons.includes('discrete-fleet-step'));
});

test('identity, revision and exact combination guards reject mixed snapshots', () => {
  const wrongTenant = clone();
  wrongTenant.scenarios[0].financial.tenant_id = 'tenant.other';
  assert.throws(() => getCommercialScenariosModel(wrongTenant), /COMMERCIAL_IDENTITY_MISMATCH/);
  assert.throws(() => getCommercialScenariosModel(fixture, 'revision.old'), /COMMERCIAL_STALE_REVISION/);
  const duplicate = clone();
  duplicate.scenarios[5].uncertainty = 'BASE';
  assert.throws(() => getCommercialScenariosModel(duplicate), /COMMERCIAL_SIX_COMBINATIONS_REQUIRED/);
});

test('version detector leaves capacity and legacy old-run viewers untouched', () => {
  assert.equal(isCommercialScenariosBundle(fixture), true);
  assert.equal(isCommercialScenariosBundle({ schema_version: 'capacity-analysis-response-v2' }), false);
  assert.equal(isCommercialScenariosBundle({ recommendations: [] }), false);
});

test('presentation schema is strict at the versioned envelope', async () => {
  const schema = JSON.parse(await readFile(new URL('contracts/commercial-scenarios-bundle-v2.schema.json', root), 'utf8'));
  assert.equal(schema.additionalProperties, false);
  assert.equal(schema.properties.schema_version.const, 'commercial-scenarios-bundle-v2');
});
