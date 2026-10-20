import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateLiveEconomics } from '../src/editor/live-economics.js';

const inputs = { staff_count: 3, monthly_employer_cost: 50_000, workdays_year: 250,
  hours_shift: 8, human_tasks_shift: 100, task_share: 1, workload_day: 50,
  realization_share: .5, robot_price: 1_000_000, integration_cost: 0,
  annual_service: 100_000, annual_energy: 20_000, discount_rate: .1, operation_seconds: 30 };
const scene = (count = 1, blocked = false) => ({
  staticObjects: Array.from({ length: count }, (_, i) => ({ kind: 'pallet_amr', id: `robot-${i}` })),
  editorAssignments: Array.from({ length: count }, (_, i) => ({ ok: !blocked, routeId: i + 1, distance: 20, speed_mps: 1 })),
  routes: Array.from({ length: count }, (_, i) => ({ id: i + 1, speed: 1 }))
});

test('робот без работы или с заблокированным маршрутом не создаёт выгоду', () => {
  const noTask = calculateLiveEconomics({ ...scene(), editorAssignments: [] }, inputs);
  assert.equal(noTask.annual_labor_saving, 0);
  assert.equal(noTask.released_fte, 0);
  const noRoute = calculateLiveEconomics(scene(1, true), inputs);
  assert.equal(noRoute.status, 'ROUTE_BLOCKED');
  assert.equal(noRoute.robot_tasks_year, 0);
  assert.equal(noRoute.annual_labor_saving, 0);
});

test('спрос ограничивает эффект второго робота, а CAPEX растёт', () => {
  const one = calculateLiveEconomics(scene(1), inputs);
  const two = calculateLiveEconomics(scene(2), inputs);
  assert.equal(one.status, 'READY_SCENARIO');
  assert.equal(one.completed_tasks_year, 50 * 250);
  assert.equal(two.completed_tasks_year, one.completed_tasks_year);
  assert.equal(two.released_fte, one.released_fte);
  assert.equal(two.capex, 2 * one.capex);
  assert.equal(one.baseline_payroll_year, 1_800_000);
  assert.equal(calculateLiveEconomics(scene(1), { ...inputs, realization_share: 0 }).annual_labor_saving, 0);
});

test('финансовые формулы 5/10 лет и неизвестная цена', () => {
  const result = calculateLiveEconomics(scene(1), { ...inputs, workload_day: 100, staff_count: 1,
    human_tasks_shift: 100, realization_share: 1, monthly_employer_cost: 35_000,
    annual_service: 100_000, annual_energy: 20_000, discount_rate: 0 });
  // 420k labor minus 120k OPEX = 300k net each year.
  assert.equal(result.annual_labor_saving, 420_000);
  assert.equal(result.roi_5, 50);
  assert.equal(result.npv_5, 500_000);
  assert.equal(result.roi_10, 200);
  assert.equal(result.npv_10, 2_000_000);
  const { robot_price, ...withoutPrice } = inputs;
  const missing = calculateLiveEconomics(scene(1), withoutPrice);
  assert.equal(missing.capex, null);
  assert.equal(missing.npv_5, null);
});
