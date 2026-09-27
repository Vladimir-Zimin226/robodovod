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
