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

// Partial inputs preserve an empty field as unknown. Validation and branch
// readiness are owned by the server and saved with the resulting run.
export function buildPartialEconomicsRunRequest({ values, capacityRequest, project, scenario, sourceRunId = null }) {
  if (!project?.id || !scenario?.id || !capacityRequest?.input_revision || !values.capacityRunId) {
    throw new Error('Откройте сохранённый расчёт мощности C11 и сценарий проекта.');
  }
  const optional = (value) => String(value ?? '').trim() || null;
  const staffing = (technicianMode) => values.controlMode && technicianMode ? {
    control_mode: values.controlMode,
    technician_mode: technicianMode,
    technician_qualification_confirmed: values.qualifiedTechTransfer === true,
    ...(values.controlMode === 'TRANSFER' && optional(values.controlTransferSupplement) !== null
      ? { control_transfer_monthly_supplement_gross: optional(values.controlTransferSupplement) } : {}),
    ...(technicianMode === 'TRANSFER' && optional(values.techTransferSupplement) !== null
      ? { technician_transfer_monthly_supplement_gross: optional(values.techTransferSupplement) } : {}),
    ...(technicianMode === 'CONTRACTOR' ? { technician_contractor_annual_gross: optional(values.technicianContractorAnnual) } : {}),
    source: 'USER', provenance_ref: 'input.economics.staffing-decision',
  } : null;
  const fields = {
    evaluation_date: optional(values.evaluationDate), horizon_years: optional(values.horizonYears),
    discount_rate: optional(values.discountRate),
    primary_role_id: optional(values.primaryRoleId) || capacityRequest.process?.role_refs?.[0] || null,
    manual_units_per_shift: capacityRequest.process?.scope === 'CLEANING_AREA' ? null : optional(values.manualUnitsPerShift),
    role_salaries_confirmed_as_monthly_gross: values.grossConfirm === true,
    control_headcount: optional(values.controlHeadcount), control_monthly_gross: optional(values.controlMonthlyGross),
    technician_headcount: optional(values.technicianHeadcount), technician_monthly_gross: optional(values.technicianMonthlyGross),
    organizer_price_currency_rub_confirmed: values.currencyConfirm === true,
    purchase_price_override_gross: optional(values.purchasePriceOverride),
    purchase_price_source: optional(values.purchasePriceSource),
    implementation_cost_total_gross: optional(values.implementationCost), annual_service_per_robot_gross: optional(values.annualService),
    warranty_years: optional(values.warrantyYears), average_power_w: optional(values.averagePowerW),
    initial_battery_in_robot_price_confirmed: values.initialBatteryConfirm === true,
    battery_replacements_in_service_confirmed: values.batteryServiceConfirm === true,
    shared_site_capital_gross: optional(values.sharedSiteCapital), shared_annual_cost_gross: optional(values.sharedAnnualCost),
    raas_monthly_per_robot_gross: optional(values.raasMonthly), raas_contract_months: optional(values.raasContractMonths),
    raas_infrastructure_owner: optional(values.raasInfrastructureOwner), raas_vendor_scope_confirmed: values.raasScopeConfirm === true,
    start_seconds_from_midnight: optional(values.startSeconds), timezone: optional(values.timezone),
  };
  const numericFields = [
    'horizon_years', 'discount_rate', 'manual_units_per_shift', 'control_headcount',
    'control_monthly_gross', 'technician_headcount', 'technician_monthly_gross',
    'implementation_cost_total_gross', 'annual_service_per_robot_gross',
    'purchase_price_override_gross',
    'warranty_years', 'average_power_w', 'shared_site_capital_gross',
    'shared_annual_cost_gross', 'raas_monthly_per_robot_gross',
    'raas_contract_months', 'start_seconds_from_midnight',
  ];
  const field_sources = Object.fromEntries(numericFields.filter((field) => fields[field] !== null)
    .map((field) => [field, values.sources?.[field] === 'ASSUMPTION' ? 'ASSUMPTION' : 'USER']));
  const assumption_evidence = Object.fromEntries(Object.entries(values.assumptions || {}).filter(
    ([field, evidence]) => field_sources[field] === 'ASSUMPTION' && evidence,
  ));
  return {
    scenario_id: scenario.id, capacity_run_id: values.capacityRunId,
    ...(sourceRunId ? { source_run_id: sourceRunId } : {}),
    input: { schema_version: 'economics-explicit-inputs-v5', input_revision: capacityRequest.input_revision,
      ...(values.calculationDepth ? { calculation_depth: values.calculationDepth } : {}),
      ...fields, staffing_purchase: staffing(values.technicianPurchaseMode),
      staffing_raas: staffing(values.technicianRaasMode), field_sources, assumption_evidence },
  };
}
