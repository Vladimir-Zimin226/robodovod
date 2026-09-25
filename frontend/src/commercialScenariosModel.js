export const COMMERCIAL_SCENARIOS_SCHEMA = 'commercial-scenarios-bundle-v2';
import { formatDecimal } from './displayNumber.js';

export const ACQUISITIONS = Object.freeze(['PURCHASE', 'RAAS']);
export const UNCERTAINTIES = Object.freeze(['PESSIMISTIC', 'BASE', 'OPTIMISTIC']);

const METRIC_STATUS = new Set(['COMPLETE', 'NOT_REACHED', 'N_A', 'INCOMPLETE']);
const FINANCE_SCHEMAS = Object.freeze({
  PURCHASE: 'financial-result-v1',
  RAAS: 'raas-financial-result-v1',
});

function contractError(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function requireObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw contractError(code);
  return value;
}

function requireString(value, code) {
  if (typeof value !== 'string' || value.length === 0) throw contractError(code);
  return value;
}

function requireArray(value, code) {
  if (!Array.isArray(value)) throw contractError(code);
  return value;
}

function assertMetric(metric, code) {
  requireObject(metric, code);
  if (!METRIC_STATUS.has(metric.status)) throw contractError(`${code}_STATUS`);
  if (metric.status === 'COMPLETE' && typeof metric.value !== 'string') {
    throw contractError(`${code}_VALUE`);
  }
  if (metric.status !== 'COMPLETE' && metric.value !== null) throw contractError(`${code}_NULL`);
  return metric;
}

function assertScenario(scenario, identities) {
  requireObject(scenario, 'COMMERCIAL_SCENARIO_INVALID');
  if (!ACQUISITIONS.includes(scenario.acquisition)) throw contractError('COMMERCIAL_ACQUISITION_INVALID');
  if (!UNCERTAINTIES.includes(scenario.uncertainty)) throw contractError('COMMERCIAL_UNCERTAINTY_INVALID');
  if (scenario.procurement?.source_schema_version !== 'procurement-report-v1') {
    throw contractError('COMMERCIAL_PROCUREMENT_VERSION');
  }
  if (scenario.financial?.source_schema_version !== FINANCE_SCHEMAS[scenario.acquisition]) {
    throw contractError('COMMERCIAL_FINANCIAL_VERSION');
  }
  if (scenario.allocation?.source_schema_version !== 'multiprocess-allocation-result-v1') {
    throw contractError('COMMERCIAL_ALLOCATION_VERSION');
  }
  for (const source of [scenario.financial, scenario.allocation]) {
    if (source.project_id !== identities.projectId || source.tenant_id !== identities.tenantId) {
      throw contractError('COMMERCIAL_IDENTITY_MISMATCH');
    }
    if (source.input_revision !== identities.revision) throw contractError('COMMERCIAL_REVISION_MISMATCH');
  }
  if (scenario.procurement.acquisition !== scenario.acquisition) {
    throw contractError('COMMERCIAL_PROCUREMENT_ACQUISITION_MISMATCH');
  }
  assertMetric(scenario.financial.npv_project, 'COMMERCIAL_NPV');
  assertMetric(scenario.financial.simple_payback, 'COMMERCIAL_SIMPLE_PAYBACK');
  assertMetric(scenario.financial.discounted_payback, 'COMMERCIAL_DISCOUNTED_PAYBACK');
  requireArray(scenario.financial.annual_ledgers, 'COMMERCIAL_ANNUAL_LEDGERS');
  requireArray(scenario.expenses, 'COMMERCIAL_EXPENSES');
  requireArray(scenario.assumptions, 'COMMERCIAL_ASSUMPTIONS');
  requireArray(scenario.source_refs, 'COMMERCIAL_SOURCE_REFS');
  const recommendation = requireObject(scenario.recommendation, 'COMMERCIAL_RECOMMENDATION');
  if (recommendation.status === 'RECOMMENDED' && (
    scenario.financial.status !== 'COMPLETE'
    || scenario.procurement.procurement_ready !== true
    || !recommendation.candidate_id
  )) throw contractError('COMMERCIAL_FALSE_RECOMMENDATION');
  return scenario;
}

export function assertCommercialScenariosBundle(bundle, expectedRevision = null) {
  requireObject(bundle, 'COMMERCIAL_BUNDLE_INVALID');
  if (bundle.schema_version !== COMMERCIAL_SCENARIOS_SCHEMA) throw contractError('COMMERCIAL_SCHEMA_VERSION');
  const identities = {
    projectId: requireString(bundle.project_id, 'COMMERCIAL_PROJECT_ID'),
    tenantId: requireString(bundle.tenant_id, 'COMMERCIAL_TENANT_ID'),
    revision: requireString(bundle.input_revision, 'COMMERCIAL_INPUT_REVISION'),
  };
  if (expectedRevision && expectedRevision !== identities.revision) throw contractError('COMMERCIAL_STALE_REVISION');
  if (bundle.sensitivity?.source_schema_version !== 'sensitivity-result-v1') {
    throw contractError('COMMERCIAL_SENSITIVITY_VERSION');
  }
  if (bundle.ranking?.source_schema_version !== 'ranking-result-v2') throw contractError('COMMERCIAL_RANKING_VERSION');
  if (bundle.sensitivity.project_id !== identities.projectId || bundle.sensitivity.tenant_id !== identities.tenantId) {
    throw contractError('COMMERCIAL_SENSITIVITY_IDENTITY');
  }
  const roles = requireArray(bundle.roles, 'COMMERCIAL_ROLES');
  for (const role of roles) {
    requireString(role.role_id, 'COMMERCIAL_ROLE_ID');
    const salary = requireObject(role.monthly_gross_salary, 'COMMERCIAL_ROLE_SALARY');
    if (!['KNOWN', 'MISSING'].includes(salary.status)) throw contractError('COMMERCIAL_ROLE_SALARY_STATUS');
    if ((salary.status === 'KNOWN') !== (typeof salary.value === 'string')) {
      throw contractError('COMMERCIAL_ROLE_SALARY_VALUE');
    }
    if (salary.source !== 'USER' && salary.status === 'KNOWN') throw contractError('COMMERCIAL_ROLE_SALARY_SOURCE');
  }
  const scenarios = requireArray(bundle.scenarios, 'COMMERCIAL_SCENARIOS');
  const combinations = scenarios.map((scenario) => `${scenario.acquisition}:${scenario.uncertainty}`);
  const expected = ACQUISITIONS.flatMap((acquisition) => (
    UNCERTAINTIES.map((uncertainty) => `${acquisition}:${uncertainty}`)
  ));
  if (scenarios.length !== 6 || new Set(combinations).size !== 6 || expected.some((key) => !combinations.includes(key))) {
    throw contractError('COMMERCIAL_SIX_COMBINATIONS_REQUIRED');
  }
  scenarios.forEach((scenario) => assertScenario(scenario, identities));
  return bundle;
}

export function isCommercialScenariosBundle(value) {
  return value?.schema_version === COMMERCIAL_SCENARIOS_SCHEMA;
}

export function formatServerMoney(value, unit = 'RUB') {
  if (value == null) return '—';
  const number = formatDecimal(value, 2, 2);
  return number == null ? '—' : `${number} ${unit === 'RUB' ? '₽' : unit}`;
}

export function formatServerMetric(metric) {
  assertMetric(metric, 'COMMERCIAL_DISPLAY_METRIC');
  if (metric.status === 'NOT_REACHED') return 'Не достигнута';
  if (metric.status === 'INCOMPLETE') return 'Недостаточно данных';
  if (metric.status === 'N_A') return 'Не применяется';
  return metric.unit === 'RUB' ? formatServerMoney(metric.value) : `${formatDecimal(metric.value) ?? '—'} ${metric.unit === 'YEAR' ? 'лет' : metric.unit}`;
}

function scenarioLabel(acquisition, uncertainty) {
  const acquisitionLabel = acquisition === 'PURCHASE' ? 'Покупка' : 'RaaS';
  const uncertaintyLabel = {
    PESSIMISTIC: 'Пессимистичный', BASE: 'Базовый', OPTIMISTIC: 'Оптимистичный',
  }[uncertainty];
  return `${acquisitionLabel} · ${uncertaintyLabel}`;
}

function procurementView(report) {
  const raw = report.money?.raw_money;
  return {
    status: report.procurement_status,
    ready: report.procurement_ready,
    blockers: report.blockers || [],
    cashGross: report.money?.cash_gross_rub || null,
    rawAmount: raw?.raw_amount || null,
    currency: raw?.currency || 'UNKNOWN',
    taxBasis: raw?.tax_basis || 'UNKNOWN',
    vatRate: raw?.vat_rate ?? null,
    sourceId: raw?.source?.source_id || null,
    supplyRisk: report.supply_risk,
  };
}

function financialView(result) {
  return {
    status: result.status,
    npvProject: formatServerMetric(result.npv_project),
    simplePayback: formatServerMetric(result.simple_payback),
    discountedPayback: formatServerMetric(result.discounted_payback),
    annualLedgers: result.annual_ledgers.map((ledger) => ({
      year: ledger.year,
      baseline: ledger.primary_cf_base,
      scenario: ledger.primary_cf_scenario,
      delta: ledger.differential_cf,
      status: ledger.status,
      sourceRefs: ledger.source_refs || [],
    })),
  };
}

export function getCommercialScenariosModel(bundle, expectedRevision = null) {
  assertCommercialScenariosBundle(bundle, expectedRevision);
  return {
    schemaVersion: bundle.schema_version,
    runId: bundle.run_id,
    projectId: bundle.project_id,
    tenantId: bundle.tenant_id,
    revision: bundle.input_revision,
    roles: bundle.roles.map((role) => ({ ...role })),
    scenarios: bundle.scenarios.map((scenario) => ({
      id: scenario.scenario_id,
      key: `${scenario.acquisition}:${scenario.uncertainty}`,
      label: scenarioLabel(scenario.acquisition, scenario.uncertainty),
      acquisition: scenario.acquisition,
      uncertainty: scenario.uncertainty,
      procurement: procurementView(scenario.procurement),
      financial: financialView(scenario.financial),
      recommendation: { ...scenario.recommendation },
      allocation: scenario.allocation,
      expenses: scenario.expenses.map((line) => ({ ...line })),
      assumptions: scenario.assumptions.map((item) => ({ ...item })),
      sourceRefs: [...scenario.source_refs],
    })),
    sensitivity: bundle.sensitivity.variants.map((variant) => ({
      id: variant.variant_id,
      parameter: variant.override.parameter_id,
      direction: variant.override.direction,
      status: variant.status,
      deltaNpv: variant.npv_project.delta_value,
      unit: variant.npv_project.unit,
      reasons: [...variant.step_reasons],
    })),
    ranking: {
      technical: { ...bundle.ranking.technical_recommendation },
      financial: { ...bundle.ranking.financial_recommendation },
    },
    versions: { ...bundle.versions },
    limitations: [...bundle.limitations],
  };
}

export function createCommercialSession(bundle) {
  const model = getCommercialScenariosModel(bundle);
  const purchase = model.scenarios.find((item) => item.acquisition === 'PURCHASE');
  const raas = model.scenarios.find((item) => item.acquisition === 'RAAS');
  return {
    stale: false,
    dirtyFields: [],
    result: model,
    inputs: {
      purchasePrice: purchase?.procurement.rawAmount || '',
      purchaseTaxBasis: purchase?.procurement.taxBasis || 'UNKNOWN',
      raasRate: raas?.procurement.rawAmount || '',
      raasTaxBasis: raas?.procurement.taxBasis || 'UNKNOWN',
      roleSalaries: Object.fromEntries(model.roles.map((role) => [
        role.role_id, role.monthly_gross_salary.value || '',
      ])),
    },
  };
}

export function applyCommercialInputEdit(session, field, value) {
  const nextInputs = structuredClone(session.inputs);
  if (field.startsWith('roleSalaries.')) {
    nextInputs.roleSalaries[field.slice('roleSalaries.'.length)] = value;
  } else if (Object.hasOwn(nextInputs, field)) {
    nextInputs[field] = value;
  } else {
    throw contractError('COMMERCIAL_INPUT_FIELD_UNKNOWN');
  }
  return {
    inputs: nextInputs,
    result: null,
    stale: true,
    dirtyFields: [...new Set([...session.dirtyFields, field])].sort(),
  };
}
