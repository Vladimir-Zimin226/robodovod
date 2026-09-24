const DECIMAL = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;

function requiredDecimal(value, field, { positive = false } = {}) {
  const raw = String(value ?? '').trim();
  if (!DECIMAL.test(raw) || (positive && Number(raw) <= 0)) {
    const error = new Error(`Заполните поле «${field}» допустимым числом.`);
    error.code = 'ECONOMICS_INPUT_INVALID';
    throw error;
  }
  return raw;
}

function requiredInteger(value, field, minimum = 0) {
  const raw = String(value ?? '').trim();
  if (!/^\d+$/.test(raw) || Number(raw) < minimum) {
    const error = new Error(`Заполните поле «${field}» целым числом.`);
    error.code = 'ECONOMICS_INPUT_INVALID';
    throw error;
  }
  return Number(raw);
}

export function buildEconomicsRunRequest({ values, capacityRequest, project, scenario }) {
  if (!project?.id || !scenario?.id || !capacityRequest?.input_revision) {
    throw new Error('Не найден проект, сценарий или immutable C11 snapshot.');
  }
  const scope = capacityRequest.process?.scope;
  const manual = scope === 'CLEANING_AREA'
    ? null
    : requiredDecimal(values.manualUnitsPerShift, 'ручная производительность за смену', { positive: true });
  const confirmations = [
    ['grossConfirm', 'monthly gross'], ['currencyConfirm', 'валюта organizer price'],
    ['initialBatteryConfirm', 'батарея в цене'], ['batteryServiceConfirm', 'замена батареи в сервисе'],
    ['raasScopeConfirm', 'состав RaaS-тарифа'],
  ];
  const missing = confirmations.find(([key]) => values[key] !== true);
  if (missing) throw new Error(`Нужно явно подтвердить: ${missing[1]}.`);
  const roleRefs = capacityRequest.process?.role_refs || [];
  if (roleRefs.length > 1 && !values.primaryRoleId) throw new Error('Выберите основную роль процесса.');
  return {
    scenario_id: scenario.id,
    capacity_run_id: values.capacityRunId,
    input: {
      schema_version: 'economics-explicit-inputs-v1',
      input_revision: capacityRequest.input_revision,
      evaluation_date: values.evaluationDate,
      horizon_years: requiredInteger(values.horizonYears, 'горизонт', 5),
      discount_rate: requiredDecimal(values.discountRate, 'ставка дисконтирования'),
      primary_role_id: values.primaryRoleId || roleRefs[0] || null,
      manual_units_per_shift: manual,
      role_salaries_confirmed_as_monthly_gross: values.grossConfirm,
      control_headcount: requiredInteger(values.controlHeadcount, 'текущие диспетчеры'),
      control_monthly_gross: requiredDecimal(values.controlMonthlyGross, 'gross диспетчера'),
      technician_headcount: requiredInteger(values.technicianHeadcount, 'текущие техники'),
      technician_monthly_gross: requiredDecimal(values.technicianMonthlyGross, 'gross техника'),
      organizer_price_currency_rub_confirmed: values.currencyConfirm,
      implementation_cost_total_gross: requiredDecimal(values.implementationCost, 'внедрение gross'),
      annual_service_per_robot_gross: requiredDecimal(values.annualService, 'сервис gross'),
      warranty_years: requiredInteger(values.warrantyYears, 'гарантия'),
      average_power_w: requiredDecimal(values.averagePowerW, 'средняя мощность', { positive: true }),
      initial_battery_in_robot_price_confirmed: values.initialBatteryConfirm,
      battery_replacements_in_service_confirmed: values.batteryServiceConfirm,
      shared_site_capital_gross: requiredDecimal(values.sharedSiteCapital, 'общеплощадочный CAPEX'),
      shared_annual_cost_gross: requiredDecimal(values.sharedAnnualCost, 'общеплощадочный OPEX'),
      raas_monthly_per_robot_gross: requiredDecimal(values.raasMonthly, 'RaaS-тариф'),
      raas_contract_months: requiredInteger(values.raasContractMonths, 'срок RaaS', 1),
      raas_infrastructure_owner: values.raasInfrastructureOwner,
      raas_vendor_scope_confirmed: values.raasScopeConfirm,
      start_seconds_from_midnight: requiredInteger(values.startSeconds, 'начало окна'),
      timezone: values.timezone,
    },
  };
}
