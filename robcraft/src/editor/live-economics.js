import { ASSIGNABLE_ROBOTS } from './operational.js';

export const ECONOMICS_FIELDS = Object.freeze(['staff_count', 'monthly_employer_cost', 'workdays_year', 'hours_shift',
  'human_tasks_shift', 'task_share', 'workload_day', 'realization_share', 'robot_price', 'integration_cost',
  'annual_service', 'annual_energy', 'discount_rate', 'operation_seconds']);

const finite = value => typeof value === 'number' && Number.isFinite(value);

export function validateEconomicsInputs(inputs) {
  if (!inputs || typeof inputs !== 'object' || Array.isArray(inputs) || Object.keys(inputs).some(key => !ECONOMICS_FIELDS.includes(key))) throw new TypeError('Неверные поля живой экономики');
  for (const [key, value] of Object.entries(inputs)) {
    if (!finite(value) || value < 0 || (['task_share', 'realization_share', 'discount_rate'].includes(key) && value > 1))
      throw new TypeError(`Неверное значение ${key}`);
  }
  return inputs;
}

const money = (inputs, key) => finite(inputs[key]) ? inputs[key] : null;
const all = (inputs, keys) => keys.every(key => finite(inputs[key]));

export function calculateLiveEconomics(scene, inputs = {}) {
  validateEconomicsInputs(inputs);
  const placedRobots = scene.staticObjects.filter(item => ASSIGNABLE_ROBOTS[item.kind]).length;
  const assignments = scene.editorAssignments || [];
  const active = assignments.filter(item => item.ok);
  const blocked = assignments.filter(item => !item.ok);
  const routeById = new Map(scene.routes.map(route => [route.id, route]));
  const base = {
    status: blocked.length && !active.length ? 'ROUTE_BLOCKED' : active.length ? 'PARTIAL' : 'EMPTY',
    placed_robots: placedRobots, active_robots: active.length, blocked_robots: blocked.length,
    baseline_payroll_year: all(inputs, ['staff_count', 'monthly_employer_cost']) ? inputs.staff_count * inputs.monthly_employer_cost * 12 : null,
    capex: money(inputs, 'robot_price') === null ? null : placedRobots * inputs.robot_price + (money(inputs, 'integration_cost') ?? 0),
    opex_year: all(inputs, ['annual_service', 'annual_energy']) ? inputs.annual_service + inputs.annual_energy : null,
    robot_tasks_year: 0, completed_tasks_year: null, potential_released_hours: null,
    realized_released_hours: null, released_fte: null, annual_labor_saving: null,
    payback_years: null, roi_5: null, roi_10: null, npv_5: null, npv_10: null,
    missing: []
  };
  const required = ['staff_count', 'monthly_employer_cost', 'workdays_year', 'hours_shift', 'human_tasks_shift',
    'task_share', 'workload_day', 'realization_share', 'robot_price', 'integration_cost', 'annual_service',
    'annual_energy', 'discount_rate', 'operation_seconds'];
  base.missing = required.filter(key => !finite(inputs[key]));
  if (!active.length) {
    Object.assign(base, { potential_released_hours: 0, realized_released_hours: 0, released_fte: 0, annual_labor_saving: 0 });
    return base;
  }
  if (base.missing.length) return base;
  if (inputs.hours_shift <= 0 || inputs.human_tasks_shift <= 0 || inputs.workdays_year <= 0 || inputs.staff_count <= 0 || inputs.robot_price <= 0) {
    base.status = 'PARTIAL'; base.missing.push('Положительные значения смены, выработки, дней, штата и цены'); return base;
  }
  const annualWorkload = inputs.workload_day * inputs.workdays_year;
  const robotCapacity = active.reduce((sum, assignment) => {
    const route = routeById.get(assignment.routeId);
    const cycle = assignment.distance / (route?.speed || assignment.speed_mps) + inputs.operation_seconds;
    return sum + (cycle > 0 ? inputs.hours_shift * 3600 * inputs.workdays_year / cycle : 0);
  }, 0);
  const completed = Math.min(annualWorkload, robotCapacity);
  const humanRate = inputs.human_tasks_shift / inputs.hours_shift;
  const potentialHours = completed / humanRate;
  const allocatedHours = inputs.staff_count * inputs.workdays_year * inputs.hours_shift * inputs.task_share;
  const eligibleHours = Math.min(potentialHours, annualWorkload / humanRate, allocatedHours);
  const realizedHours = eligibleHours * inputs.realization_share;
  const annualPaidHours = inputs.workdays_year * inputs.hours_shift;
  const fte = Math.min(inputs.staff_count, realizedHours / annualPaidHours);
  const saving = fte * inputs.monthly_employer_cost * 12;
  const net = saving - base.opex_year;
  const capex = base.capex;
  const roi = years => (net * years - capex) / capex * 100;
  const npv = years => -capex + Array.from({ length: years }, (_, i) => net / (1 + inputs.discount_rate) ** (i + 1)).reduce((sum, value) => sum + value, 0);
  Object.assign(base, { status: 'READY_SCENARIO', robot_tasks_year: robotCapacity, completed_tasks_year: completed,
    potential_released_hours: potentialHours, realized_released_hours: realizedHours, released_fte: fte,
    annual_labor_saving: saving, payback_years: net > 0 ? capex / net : null,
    roi_5: roi(5), roi_10: roi(10), npv_5: npv(5), npv_10: npv(10), missing: [] });
  return base;
}
