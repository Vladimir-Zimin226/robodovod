import test from 'node:test';
import assert from 'node:assert/strict';
import { economicsReadiness } from '../src/economicsReadiness.js';

const fields = [
  ['Труд', 'manualUnitsPerShift', 'manual_units_per_shift'],
  ...['control_headcount', 'control_monthly_gross', 'technician_headcount', 'technician_monthly_gross',
    'horizon_years', 'discount_rate', 'implementation_cost_total_gross', 'annual_service_per_robot_gross',
    'warranty_years', 'average_power_w', 'shared_site_capital_gross', 'shared_annual_cost_gross',
    'raas_monthly_per_robot_gross', 'raas_contract_months', 'start_seconds_from_midnight'].map((server) => ['', server, server]),
];

test('five independent conditions and unknown amounts keep full run unavailable', () => {
  const values = Object.fromEntries(fields.map(([, key]) => [key, '0']));
  values.manualUnitsPerShift = '100';
  values.average_power_w = '1000'; values.horizon_years = '5'; values.raas_contract_months = '60';
  values.evaluationDate = '2026-09-25'; values.raasInfrastructureOwner = 'CUSTOMER'; values.timezone = 'Asia/Sakhalin';
  values.controlMode = 'HIRE'; values.technicianPurchaseMode = 'HIRE'; values.technicianRaasMode = 'HIRE';
  const capacityRequest = { process: { scope: 'TRANSPORT_CYCLE', role_refs: ['driver'] } };
  let preview = economicsReadiness(values, capacityRequest, fields);
  assert.equal(preview.fullReady, false);
  assert.equal(preview.missingConditions.length, 5);
  values.grossConfirm = true; values.currencyConfirm = true; values.initialBatteryConfirm = true;
  values.batteryServiceConfirm = true; values.raasScopeConfirm = true;
  preview = economicsReadiness(values, capacityRequest, fields);
  assert.equal(preview.fullReady, true);
  values.raas_monthly_per_robot_gross = '';
  preview = economicsReadiness(values, capacityRequest, fields);
  assert.equal(preview.fullReady, false);
  assert.ok(preview.branches.find((branch) => branch.key === 'raas').missing.includes('raas_monthly_per_robot_gross'));
});
