import test from 'node:test';
import assert from 'node:assert/strict';
import { buildEconomicsRunRequest } from '../src/economicsInputV2.js';

const values = {
  capacityRunId: '00000000-0000-0000-0000-000000000001', evaluationDate: '2026-09-24',
  horizonYears: '5', discountRate: '0.15', primaryRoleId: '', manualUnitsPerShift: '100',
  grossConfirm: true, controlHeadcount: '0', controlMonthlyGross: '100000',
  technicianHeadcount: '0', technicianMonthlyGross: '120000', currencyConfirm: true,
  implementationCost: '500000', annualService: '120000', warrantyYears: '1',
  averagePowerW: '1000', initialBatteryConfirm: true, batteryServiceConfirm: true,
  sharedSiteCapital: '0', sharedAnnualCost: '0', raasMonthly: '180000',
  raasContractMonths: '60', raasInfrastructureOwner: 'VENDOR', raasScopeConfirm: true,
  startSeconds: '0', timezone: 'Europe/Moscow',
};
const capacityRequest = {
  input_revision: 'revision.v1',
  process: { scope: 'TRANSPORT_CYCLE', role_refs: ['role.driver'] },
};

test('serializes only explicit C13-C21 inputs and capacity binding', () => {
  const result = buildEconomicsRunRequest({
    values, capacityRequest, project: { id: 'project.1' }, scenario: { id: 'scenario.1' },
  });
  assert.equal(result.capacity_run_id, values.capacityRunId);
  assert.equal(result.input.manual_units_per_shift, '100');
  assert.equal(result.input.primary_role_id, 'role.driver');
  assert.equal(result.input.control_monthly_gross, '100000');
  assert.equal(result.input.schema_version, 'economics-explicit-inputs-v1');
  assert.equal('fte_cost_rub' in result.input, false);
});

test('does not silently accept unknown commercial basis', () => {
  assert.throws(() => buildEconomicsRunRequest({
    values: { ...values, currencyConfirm: false }, capacityRequest,
    project: { id: 'project.1' }, scenario: { id: 'scenario.1' },
  }), /валюта organizer price/);
  assert.throws(() => buildEconomicsRunRequest({
    values: { ...values, annualService: '' }, capacityRequest,
    project: { id: 'project.1' }, scenario: { id: 'scenario.1' },
  }), /сервис gross/);
});
