import assert from 'node:assert/strict';
import test from 'node:test';
import { buildWhatIfInput, DEFAULT_WHAT_IF, scaleDecimal, whatIfChanged, whatIfSummary } from '../src/whatIfModel.js';

test('what-if decimal scale is exact and an unchanged branch preserves the base', () => {
  assert.equal(scaleDecimal('9007199254740993.25', 20, 2), '10808639105689191.9');
  assert.equal(scaleDecimal(null, 20), null);
  assert.equal(whatIfChanged(DEFAULT_WHAT_IF), false);
  assert.equal(whatIfChanged({ ...DEFAULT_WHAT_IF, volumePercent: 10 }), true);
});

test('object branch changes price, labor, route speed and demand without mutating base', () => {
  const input = { kind: 'WAREHOUSE', general: { annual_service_share: '0.1', integration_share: '0.2',
    discount_rate: '0.15', realizable_labor_share: '0.5', fleet_reserve_share: '0.1', horizon_years: 5 },
  roles: [{ monthly_employer_cost_rub: '100000', realizable_labor_share: '0.5', works: [{
    daily_volume: '875', robot_units_per_hour: '35', scenario_purchase_price_rub: '2000000',
    raas_mode: 'PERCENT', raas_percent_monthly: '2', rate_source: 'SCENARIO_ASSUMPTION',
    simulation: { speed_loaded_mps: 1, speed_empty_mps: 1, pickup_service_s: 30 },
  }] }] };
  const snapshot = structuredClone(input);
  const branch = buildWhatIfInput(input, { kind: 'WAREHOUSE' }, { ...DEFAULT_WHAT_IF,
    pricePercent: 20, laborPercent: 10, volumePercent: 40, speedPercent: -20, horizonYears: 10 });
  assert.deepEqual(input, snapshot);
  assert.equal(branch.roles[0].works[0].daily_volume, '1225');
  assert.equal(branch.roles[0].works[0].scenario_purchase_price_rub, '2400000');
  assert.equal(branch.roles[0].works[0].simulation.speed_loaded_mps, '0.8');
  assert.equal(branch.roles[0].works[0].simulation.pickup_service_s, 30);
  assert.equal(branch.roles[0].monthly_employer_cost_rub, '110000');
  assert.equal(branch.general.horizon_years, 10);
});

test('warehouse branch uses selected candidate override and keeps an unknown price unknown', () => {
  const input = { general: { annual_service_share: '0.1', integration_share: '0.2',
    discount_rate: '0.15', realizable_labor_share: '0.5', fleet_reserve_share: '0.1', horizon_years: 5 },
  roles: [{ role_code: 'forklift_driver', daily_volume: '875', monthly_employer_cost_rub: '100000',
    simulation: { speed_loaded_mps: 1, speed_empty_mps: 1 } }], overrides: [] };
  const report = { roles: [{ role_code: 'forklift_driver', selected_position_id: 'transport', candidates: [{
    position_id: 'transport', price_rub: '2000000', robot_units_per_hour: '35', raas_mode: 'PERCENT',
    raas_percent_monthly: '2',
  }] }] };
  const branch = buildWhatIfInput(input, report, { ...DEFAULT_WHAT_IF,
    pricePercent: 20, volumePercent: 40, speedPercent: -20, rentPercent: 25 });
  assert.equal(branch.roles[0].daily_volume, '1225');
  assert.equal(branch.roles[0].simulation.speed_loaded_mps, '0.8');
  assert.deepEqual(branch.overrides, [{ role_code: 'forklift_driver', position_id: 'transport',
    price_rub: '2400000', omit_purchase_price: false, units_per_hour: '28',
    raas_percent_monthly: '2.5', omit_raas_tariff: false }]);
  const missing = buildWhatIfInput(input, { roles: [{ ...report.roles[0],
    candidates: [{ ...report.roles[0].candidates[0], price_rub: null }] }] },
  { ...DEFAULT_WHAT_IF, pricePercent: 20 });
  assert.equal(missing.overrides[0].price_rub, undefined);
  assert.equal(input.overrides.length, 0);
});

test('comparison reads server portfolio fields and keeps missing money unknown', () => {
  const report = { kind: 'WAREHOUSE', base_total: { fleet: 2, fte_equivalent: '1',
    purchase: { capex_rub: null, npv_rub: null, roi_percent: null, payback_years: null },
    raas: { capex_rub: '0', npv_rub: '500', roi_percent: null, roi_status: 'N/A: CAPEX заказчика равен нулю' } },
  roles: [{ works: [] }] };
  const summary = whatIfSummary(report);
  assert.equal(summary.purchase.npv, null);
  assert.equal(summary.raas.roiStatus, 'N/A: CAPEX заказчика равен нулю');
});
