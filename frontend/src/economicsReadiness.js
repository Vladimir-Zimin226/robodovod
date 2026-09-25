// A navigation preview only. The saved branch status is decided by the server.
export const ECONOMICS_CONDITIONS = Object.freeze([
  { key: 'grossConfirm', group: 'Труд', consequence: 'Без этого не рассчитывается труд и зависимые денежные ветки.' },
  { key: 'currencyConfirm', group: 'Покупка', consequence: 'Без этого не рассчитывается покупка.' },
  { key: 'initialBatteryConfirm', group: 'Покупка', consequence: 'Без этого состав CAPEX покупки неизвестен.' },
  { key: 'batteryServiceConfirm', group: 'Покупка', consequence: 'Без этого состав OPEX покупки неизвестен.' },
  { key: 'raasScopeConfirm', group: 'RaaS', consequence: 'Без этого не рассчитывается RaaS.' },
]);

export function economicsReadiness(values, capacityRequest, fields) {
  const known = (server) => {
    const entry = fields.find((field) => field[2] === server);
    if (!entry) return false;
    const value = String(values[entry[1]] ?? '').trim();
    if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)) return false;
    const number = Number(value);
    if (['manual_units_per_shift', 'average_power_w'].includes(server) && number <= 0) return false;
    if (server === 'discount_rate' && number > 1) return false;
    const integerLimits = { horizon_years: [5, 15], warranty_years: [0, 15], raas_contract_months: [1, 180],
      control_headcount: [0, Infinity], technician_headcount: [0, Infinity], start_seconds_from_midnight: [0, 86399] };
    if (integerLimits[server] && (!Number.isInteger(number) || number < integerLimits[server][0] || number > integerLimits[server][1])) return false;
    return value !== '' && !value.includes('..') &&
      ((values.sources?.[server] || 'USER') !== 'ASSUMPTION' ||
        (values.assumptions?.[server]?.confirmed === true && values.assumptions[server].confirmed_value === value));
  };
  const missingConditions = ECONOMICS_CONDITIONS.filter((item) => values[item.key] !== true);
  const roleRefs = capacityRequest?.process?.role_refs || [];
  const cleaning = capacityRequest?.process?.scope === 'CLEANING_AREA';
  const labourMissing = [
    ...(!cleaning && !known('manual_units_per_shift') ? ['manual_units_per_shift'] : []),
    ...['control_headcount', 'control_monthly_gross', 'technician_headcount', 'technician_monthly_gross'].filter((field) => !known(field)),
    ...(values.grossConfirm ? [] : ['role_salaries_confirmed_as_monthly_gross']),
    ...((roleRefs.length > 1 && !values.primaryRoleId) || (values.primaryRoleId && !roleRefs.includes(values.primaryRoleId)) ? ['primary_role_id'] : []),
  ];
  const purchaseMissing = [
    ...['horizon_years', 'discount_rate', 'implementation_cost_total_gross', 'annual_service_per_robot_gross',
      'warranty_years', 'average_power_w', 'shared_site_capital_gross', 'shared_annual_cost_gross'].filter((field) => !known(field)),
    ...(!values.evaluationDate ? ['evaluation_date'] : []),
    ...ECONOMICS_CONDITIONS.filter((item) => item.group === 'Покупка' && values[item.key] !== true).map((item) => item.key),
    ...(labourMissing.length ? ['labour'] : []),
  ];
  const raasMissing = [
    ...purchaseMissing,
    ...['raas_monthly_per_robot_gross', 'raas_contract_months'].filter((field) => !known(field)),
    ...(!values.raasInfrastructureOwner ? ['raas_infrastructure_owner'] : []),
    ...(!values.raasScopeConfirm ? ['raasScopeConfirm'] : []),
    ...(known('raas_contract_months') && known('horizon_years') && Number(values.raasContractMonths) < Number(values.horizonYears) * 12 ? ['raas_contract_months'] : []),
  ];
  const visualMissing = [...['start_seconds_from_midnight'].filter((field) => !known(field)), ...(!values.timezone ? ['timezone'] : [])];
  return {
    missingConditions,
    branches: [
      { key: 'capacity', label: 'Технический расчёт', missing: [] },
      { key: 'labour', label: 'Труд', missing: labourMissing },
      { key: 'purchase', label: 'Покупка', missing: purchaseMissing },
      { key: 'raas', label: 'RaaS', missing: raasMissing },
    ],
    visualMissing,
    fullReady: labourMissing.length === 0 && purchaseMissing.length === 0 && raasMissing.length === 0 && visualMissing.length === 0,
  };
}
