import test from 'node:test';
import assert from 'node:assert/strict';
import { buildEconomicsRunRequest, buildPartialEconomicsRunRequest } from '../src/economicsInputV2.js';

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

test('partial request distinguishes unknown, confirmed zero and assumptions', () => {
  const result = buildPartialEconomicsRunRequest({
    values: { ...values, annualService: '', sharedSiteCapital: '0', raasMonthly: '',
      sources: { shared_site_capital_gross: 'ASSUMPTION' } },
    capacityRequest, project: { id: 'project.1' }, scenario: { id: 'scenario.1' },
  });
  assert.equal(result.input.schema_version, 'economics-explicit-inputs-v5');
  assert.equal(result.input.annual_service_per_robot_gross, null);
  assert.equal(result.input.raas_monthly_per_robot_gross, null);
  assert.equal(result.input.shared_site_capital_gross, '0');
  assert.equal(result.input.field_sources.shared_site_capital_gross, 'ASSUMPTION');
  assert.equal(result.input.field_sources.control_headcount, 'USER');
  assert.equal(result.input.field_sources.raas_monthly_per_robot_gross, undefined);
  assert.deepEqual(result.input.assumption_evidence, {});
  assert.equal('fte_cost_rub' in result.input, false);
});

test('staffing choices and qualification are preserved without an invented price', () => {
  const result = buildPartialEconomicsRunRequest({
    values: { ...values, controlMode: 'TRANSFER', controlTransferSupplement: '0',
      technicianPurchaseMode: 'TRANSFER', technicianRaasMode: 'VENDOR',
      qualifiedTechTransfer: true, techTransferSupplement: '0', technicianMonthlyGross: '' },
    capacityRequest, project: { id: 'project.1' }, scenario: { id: 'scenario.1' },
  });
  assert.equal(result.input.staffing_purchase.technician_mode, 'TRANSFER');
  assert.equal(result.input.staffing_purchase.technician_qualification_confirmed, true);
  assert.equal(result.input.staffing_raas.technician_mode, 'VENDOR');
  assert.equal(result.input.technician_monthly_gross, null);
});

test('partial request preserves a user range for server-side no-midpoint handling', () => {
  const result = buildPartialEconomicsRunRequest({
    values: { ...values, implementationCost: '500000..800000' },
    capacityRequest, project: { id: 'project.1' }, scenario: { id: 'scenario.1' },
  });
  assert.equal(result.input.implementation_cost_total_gross, '500000..800000');
});
