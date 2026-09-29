import { presentationValue } from './presentation.js';

export const SCENARIO_CONTROLS = [
  ['Коммерческие условия', 'purchase_price_override_gross', 'Цена одного робота, ₽', 0, null, 10000, 100000000],
  ['Коммерческие условия', 'implementation_cost_total_gross', 'Внедрение, ₽ всего', 0, null, 10000, 100000000],
  ['Коммерческие условия', 'implementation_percent', 'Внедрение, % цены парка', 0, 100, 0.1, 100],
  ['Коммерческие условия', 'raas_monthly_per_robot_gross', 'RaaS, ₽/робот/месяц', 0, null, 1000, 1000000],
  ['Коммерческие условия', 'raas_percent_monthly', 'RaaS, % цены одного робота в месяц', 0, 100, 0.1, 100],
  ['Коммерческие условия', 'raas_contract_months', 'Срок RaaS, месяцев', 1, 180, 1, 180],
  ['Эксплуатация и люди', 'manual_units_per_shift', 'Выработка человека выбранной роли за смену', 0, null, 1, 10000],
  ['Эксплуатация и люди', 'control_monthly_gross', 'Зарплата диспетчера gross, ₽/месяц', 0, null, 1000, 1000000],
  ['Эксплуатация и люди', 'technician_monthly_gross', 'Зарплата техника gross, ₽/месяц', 0, null, 1000, 1000000],
  ['Эксплуатация и люди', 'annual_service_per_robot_gross', 'Сервис, ₽/робот/год', 0, null, 1000, 1000000],
  ['Эксплуатация и люди', 'average_power_w', 'Средняя мощность робота, Вт', 0, null, 10, 10000],
  ['Эксплуатация и люди', 'shared_site_capital_gross', 'Общие вложения объекта, ₽', 0, null, 10000, 100000000],
  ['Эксплуатация и люди', 'shared_annual_cost_gross', 'Общие расходы объекта, ₽/год', 0, null, 10000, 10000000],
  ['Горизонт и финансы', 'horizon_years', 'Горизонт, лет', 5, 15, 1, 15],
  ['Горизонт и финансы', 'discount_rate', 'Ставка дисконтирования, доля', 0, 1, 0.01, 1],
];

export const SCENARIO_METRICS = [['capex', 'CAPEX'], ['opex_year_1', 'OPEX за год 1'],
  ['effect_year_1', 'Эффект за год 1'], ['npv', 'NPV'], ['roi', 'ROI'], ['tco', 'TCO'],
  ['simple_payback', 'Простая окупаемость'], ['discounted_payback', 'Дисконтированная окупаемость']];

export const canonicalJson = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);

export async function inputDigest(input) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(input)));
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

export function editScenarioInput(input, field, value) {
  return { ...input, [field]: value, field_sources: { ...input.field_sources, [field]: 'USER' },
    assumption_evidence: Object.fromEntries(Object.entries(input.assumption_evidence || {}).filter(([key]) => key !== field)),
    ...(field === 'purchase_price_override_gross' ? { purchase_price_source: value === '' ? null : 'Сценарное изменение пользователя' } : {}) };
}

export function scenarioInputError(input) {
  for (const [, field, label, min, max, step] of SCENARIO_CONTROLS) {
    const raw = input[field];
    if (raw == null || raw === '' || (typeof raw === 'string' && raw.includes('..'))) continue;
    const number = Number(raw);
    if (!Number.isFinite(number) || number < min || (max !== null && number > max)
      || (['horizon_years', 'raas_contract_months'].includes(field) && !Number.isInteger(number))) {
      return `Проверьте «${label}»: минимум ${min}${max === null ? '' : `, максимум ${max}`}${step === 1 ? ', целое число' : ''}.`;
    }
  }
  return '';
}

export function metricText(metric) {
  if (metric?.status === 'NOT_REACHED') return 'Окупаемость не достигнута';
  if (metric?.status === 'N_A') return 'Не применяется';
  if (metric?.status !== 'COMPLETE' || metric.value == null) return 'Нет данных';
  return presentationValue('', metric.value, metric.unit);
}
