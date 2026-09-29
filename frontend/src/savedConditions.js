import { fieldPresentation, presentationValue, sourceLabel } from './presentation.js';

const GROUPS = ['Работа и персонал', 'Покупка и эксплуатация', 'Аренда', 'Горизонт и ставка', 'Рабочее время'];
const groupFor = (key) => /raas/.test(key) ? 2 : /horizon|discount/.test(key) ? 3
  : /start_seconds|timezone|evaluation_date/.test(key) ? 4
    : /manual|control|technician|staffing|rotation|robotizable|residual/.test(key) ? 0 : 1;
const UNITS = { manual_units_per_shift: 'unit/shift', control_headcount: 'headcount', technician_headcount: 'headcount',
  horizon_years: 'YEAR', warranty_years: 'YEAR', raas_contract_months: 'мес.', average_power_w: 'Вт' };

export function savedConditions(input = {}, result = {}) {
  const rows = [];
  const add = (key, value, evidence = {}, label, unit) => rows.push({ key: `${rows.length}:${key}`,
    group: GROUPS[groupFor(key)], label: label || fieldPresentation(key).label,
    value: presentationValue(key, value, unit || UNITS[key]), explanation: fieldPresentation(key).action || '',
    source: sourceLabel(evidence), date: evidence.published_on || evidence.date || '',
    confirmed: evidence.confirmed === true });
  const excluded = new Set(['schema_version', 'assumption_evidence', 'field_sources', 'input_revision', 'primary_role_id',
    'staffing_policy', 'staffing_purchase', 'staffing_raas', 'work_share', 'purchase_price_source']);
  for (const [key, value] of Object.entries(input)) {
    if (excluded.has(key) || (value && typeof value === 'object')) continue;
    if (key === 'implementation_percent' && input.implementation_mode !== 'PERCENT'
      || key === 'implementation_cost_total_gross' && input.implementation_mode === 'PERCENT'
      || key === 'raas_percent_monthly' && input.raas_mode !== 'PERCENT'
      || key === 'raas_monthly_per_robot_gross' && input.raas_mode === 'PERCENT') continue;
    add(key, value, input.assumption_evidence?.[key] || { source: input.field_sources?.[key] });
  }
  for (const key of ['staffing_policy', 'staffing_purchase', 'staffing_raas']) {
    const item = input[key];
    if (!item) continue;
    for (const [field, value] of Object.entries(item)) {
      if (['schema_version', 'source', 'basis', 'date', 'confirmed', 'qualified_technician_transfer_confirmed'].includes(field)) continue;
      const label = field === 'control_mode' ? 'Управление' : field === 'technician_mode' ? 'Техподдержка' : fieldPresentation(field).label;
      add(field, value, item, `${fieldPresentation(key).label}: ${label}`);
      rows.at(-1).group = GROUPS[0];
    }
  }
  const share = result.work_share || input.work_share;
  if (share) {
    add('fraction', share.fraction, share, 'Роботизируемая доля работы выбранной роли'); rows.at(-1).group = GROUPS[0];
    add('residual_operations', share.residual_operations, share);
  }
  const basis = result.monetary_input_basis;
  if (basis) {
    add('purchase_price_override_gross', basis.unit_price_gross_rub, {}, 'Цена одного робота в денежной базе');
    add('implementation_cost_total_gross', basis.implementation?.amount_gross_rub, {}, 'Денежная база внедрения');
    add('raas_monthly_per_robot_gross', basis.raas?.per_robot_month_gross_rub, {}, 'Денежная база аренды на робота в месяц');
  }
  return GROUPS.map((label) => ({ label, rows: rows.filter((row) => row.group === label) })).filter((group) => group.rows.length);
}
