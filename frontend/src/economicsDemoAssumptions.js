import warehouseDemo from '../../data/scenarios/warehouse-economics-demo-v1.json' with { type: 'json' };

export const WAREHOUSE_ECONOMICS_DEMO = Object.freeze(warehouseDemo);

export function proposeDemoField(values, key, server, { enableTemplate = true } = {}) {
  const proposal = enableTemplate ? warehouseDemo.fields[server] : null;
  const userValues = { ...(values.userValues || {}) };
  if ((values.sources?.[server] || 'USER') === 'USER') userValues[server] = values[key];
  if (!proposal) {
    return { ...values, userValues, sources: { ...values.sources, [server]: 'ASSUMPTION' },
      assumptions: { ...values.assumptions, [server]: null } };
  }
  return { ...values, [key]: proposal.value, userValues,
    sources: { ...values.sources, [server]: 'ASSUMPTION' },
    assumptions: { ...values.assumptions, [server]: {
      schema_version: 'scenario-assumption-evidence-v1',
      template_id: warehouseDemo.schema_version, version: 'v1',
      source: warehouseDemo.source, rationale: proposal.rationale,
      published_on: warehouseDemo.published_on, confirmed_value: proposal.value,
      confirmed: false,
    } } };
}

export function chooseUserField(values, key, server) {
  const remembered = values.userValues?.[server];
  return { ...values, [key]: remembered ?? values[key],
    sources: { ...values.sources, [server]: 'USER' },
    assumptions: { ...values.assumptions, [server]: null } };
}

export function editEconomicsField(values, key, server, value, { enableTemplate = true } = {}) {
  if ((values.sources?.[server] || 'USER') !== 'ASSUMPTION') {
    return { ...values, [key]: value, userValues: { ...values.userValues, [server]: value } };
  }
  const proposal = enableTemplate ? warehouseDemo.fields[server] : null;
  const evidence = value === proposal?.value
    ? { ...(values.assumptions?.[server] || proposeDemoField(values, key, server).assumptions[server]), confirmed: false }
    : value ? { schema_version: 'scenario-assumption-evidence-v1', template_id: null,
      version: 'custom-v1', source: 'USER', rationale: 'Изменённое пользователем сценарное допущение',
      published_on: new Date().toISOString().slice(0, 10), confirmed_value: value, confirmed: false } : null;
  return { ...values, [key]: value, assumptions: { ...values.assumptions, [server]: evidence } };
}

export function confirmEconomicsAssumption(values, server, confirmed) {
  const evidence = values.assumptions?.[server];
  if (!evidence) return values;
  return { ...values, assumptions: { ...values.assumptions, [server]: { ...evidence, confirmed } } };
}

export function applyWarehouseEconomicsDemo(values, fields) {
  let next = { ...values };
  for (const [, key, server] of fields) next = proposeDemoField(next, key, server);
  return { ...next, evaluationDate: warehouseDemo.other_inputs.evaluation_date,
    raasInfrastructureOwner: warehouseDemo.other_inputs.raas_infrastructure_owner,
    timezone: warehouseDemo.other_inputs.timezone };
}

export function confirmAllEconomicsAssumptions(values) {
  return { ...values, assumptions: Object.fromEntries(Object.entries(values.assumptions || {}).map(([key, evidence]) => [
    key, evidence && evidence.confirmed_value ? { ...evidence, confirmed: true } : evidence,
  ])) };
}

export function applyManualProductivityEstimate(values, estimate) {
  if (estimate?.status !== 'ESTIMATE' || !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(String(estimate.value))
    || Number(estimate.value) <= 0) return values;
  const server = 'manual_units_per_shift';
  return { ...values, manualUnitsPerShift: String(estimate.value),
    userValues: { ...values.userValues, [server]: values.manualUnitsPerShift || '' },
    sources: { ...values.sources, [server]: 'ASSUMPTION' },
    assumptions: { ...values.assumptions, [server]: {
      schema_version: 'scenario-assumption-evidence-v1', template_id: null,
      version: 'custom-v1', source: 'USER',
      rationale: `${estimate.formula}; ${estimate.source_refs.join(', ')}`,
      published_on: new Date().toISOString().slice(0, 10),
      confirmed_value: String(estimate.value), confirmed: false,
    } },
  };
}

export function changeManualProductivityRole(values, primaryRoleId) {
  return { ...values, primaryRoleId, manualUnitsPerShift: '',
    sources: { ...values.sources, manual_units_per_shift: 'USER' },
    assumptions: { ...values.assumptions, manual_units_per_shift: null },
  };
}

export function applyTypicalObjectEconomics(values, fields, objectKind, estimate, processCode = 'warehouse_receiving_shipping') {
  const warehouse = objectKind === 'WAREHOUSE';
  let next = applyWarehouseEconomicsDemo(values, fields);
  if (!warehouse || processCode !== 'warehouse_receiving_shipping') {
    for (const [, key, server] of fields) {
      const proposal = warehouseDemo.fields[server];
      if (!proposal) continue;
      // Reuse only the numerical scaffold, explicitly as user-authorized estimates.
      next = editEconomicsField({ ...next, sources: { ...next.sources, [server]: 'ASSUMPTION' } }, key, server,
        next[key], { enableTemplate: false });
      next.assumptions[server].rationale = `Авторское допущение для типового ${warehouse ? 'склада' : objectKind === 'AIRPORT' ? 'аэропорта' : 'объекта клиники'}; ${proposal.rationale}. Не значение организаторов и не условие поставщика.`;
    }
    for (const [key, server, value] of [['horizonYears', 'horizon_years', warehouse ? '5' : '7'],
      ['raasContractMonths', 'raas_contract_months', warehouse ? '60' : '84'],
      ['manualUnitsPerShift', 'manual_units_per_shift', objectKind === 'AIRPORT' ? '100' : '65']]) {
      next = editEconomicsField(next, key, server, value, { enableTemplate: false });
    }
  }
  if (estimate?.status === 'ESTIMATE') next = applyManualProductivityEstimate(next, estimate);
  // Preserve local model time with matching evidence, rather than retaining the
  // warehouse template's 08:00 evidence for a user's 09:00 value.
  next = editEconomicsField(next, 'startSeconds', 'start_seconds_from_midnight',
    String(values.startSeconds || 32400), { enableTemplate: false });
  next = editEconomicsField({ ...next, sources: { ...next.sources, purchase_price_override_gross: 'ASSUMPTION' } },
    'purchasePriceOverride', 'purchase_price_override_gross', warehouse ? '2500000' : objectKind === 'AIRPORT' ? '1200000' : '1800000', { enableTemplate: false });
  next = confirmAllEconomicsAssumptions(next);
  return { ...next, calculationDepth: 'FULL', evaluationDate: new Date().toISOString().slice(0, 10),
    timezone: values.timezone,
    controlMode: 'HIRE', technicianPurchaseMode: 'HIRE', technicianRaasMode: 'VENDOR',
    grossConfirm: true, currencyConfirm: true, initialBatteryConfirm: true, batteryServiceConfirm: true,
    raasScopeConfirm: true, raasInfrastructureOwner: 'VENDOR',
    purchasePriceSource: 'Авторское допущение для типового объекта от 2026-09-28; не цена организаторов и не оферта поставщика',
  };
}
