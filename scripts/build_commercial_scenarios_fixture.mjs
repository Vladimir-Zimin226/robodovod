import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const projectId = 'project.c21';
const tenantId = 'tenant.c21';
const revision = 'revision.c21';

const metric = (status, value, unit) => ({ status, value, unit });

function procurement(acquisition, ready) {
  const purchase = acquisition === 'PURCHASE';
  return {
    source_schema_version: 'procurement-report-v1',
    source_digest: `sha256:${(purchase ? '1' : '2').repeat(64)}`,
    acquisition,
    procurement_status: ready ? 'VERIFIED' : 'UNVERIFIED',
    procurement_ready: ready,
    blockers: ready ? [] : ['COMMERCIAL_TERMS_UNVERIFIED'],
    supply_risk: ready ? 'LOW' : 'UNKNOWN',
    money: {
      status: 'RESOLVED',
      cash_gross_rub: purchase ? '3000000.00' : '180000.00',
      raw_money: {
        raw_amount: purchase ? '3000000.00' : '180000.00',
        currency: 'RUB',
        tax_basis: 'CASH_GROSS_RUB',
        vat_rate: null,
        source: { source_id: purchase ? 'input.purchase-price' : 'input.raas-rate' },
      },
    },
  };
}

function financial(acquisition, uncertainty, complete) {
  const purchase = acquisition === 'PURCHASE';
  const shift = { PESSIMISTIC: '-1500000.00', BASE: '0.00', OPTIMISTIC: '1800000.00' }[uncertainty];
  const npv = purchase
    ? { PESSIMISTIC: '5100000.00', BASE: '6600000.00', OPTIMISTIC: '8400000.00' }[uncertainty]
    : { PESSIMISTIC: '-900000.00', BASE: '1200000.00', OPTIMISTIC: '3000000.00' }[uncertainty];
  const incomplete = metric('INCOMPLETE', null, 'RUB');
  return {
    source_schema_version: purchase ? 'financial-result-v1' : 'raas-financial-result-v1',
    source_digest: `sha256:${(purchase ? '3' : '4').repeat(64)}`,
    project_id: projectId,
    tenant_id: tenantId,
    input_revision: revision,
    status: complete ? 'COMPLETE' : 'INCOMPLETE',
    npv_project: complete ? metric('COMPLETE', npv, 'RUB') : incomplete,
    simple_payback: complete
      ? metric(uncertainty === 'PESSIMISTIC' && !purchase ? 'NOT_REACHED' : 'COMPLETE', uncertainty === 'PESSIMISTIC' && !purchase ? null : '2.75', 'YEAR')
      : metric('INCOMPLETE', null, 'YEAR'),
    discounted_payback: complete ? metric('COMPLETE', '3.40', 'YEAR') : metric('INCOMPLETE', null, 'YEAR'),
    annual_ledgers: [1, 2, 3, 4, 5].map((year) => ({
      year,
      primary_cf_base: complete ? '-12000000.00' : null,
      primary_cf_scenario: complete ? `${year === 1 ? '' : ''}${purchase ? '18000000.00' : '14500000.00'}` : null,
      differential_cf: complete ? (year === 1 ? shift : purchase ? '30000000.00' : '26500000.00') : null,
      status: complete ? 'COMPLETE' : 'INCOMPLETE',
      source_refs: [`trace.${acquisition.toLowerCase()}.${uncertainty.toLowerCase()}.year-${year}`],
    })),
  };
}

function allocation(acquisition, uncertainty) {
  return {
    source_schema_version: 'multiprocess-allocation-result-v1',
    source_digest: `sha256:${(acquisition === 'PURCHASE' ? '5' : '6').repeat(64)}`,
    project_id: projectId,
    tenant_id: tenantId,
    input_revision: revision,
    role_conservation: [
      { role_id: 'role.operator', headcount: 20, released: uncertainty === 'OPTIMISTIC' ? 12 : 10, remaining: uncertainty === 'OPTIMISTIC' ? 8 : 10 },
      { role_id: 'role.tech', headcount: 1, released: 0, remaining: 1 },
    ],
    control_required_once: 3,
    technicians_required_once: 1,
  };
}

function scenario(acquisition, uncertainty) {
  const ready = acquisition === 'PURCHASE';
  const complete = acquisition === 'PURCHASE' || uncertainty !== 'PESSIMISTIC';
  const recommended = acquisition === 'PURCHASE' && uncertainty === 'BASE';
  return {
    scenario_id: `scenario.${acquisition.toLowerCase()}.${uncertainty.toLowerCase()}`,
    acquisition,
    uncertainty,
    procurement: procurement(acquisition, ready),
    financial: financial(acquisition, uncertainty, complete),
    allocation: allocation(acquisition, uncertainty),
    recommendation: {
      status: recommended ? 'RECOMMENDED' : complete ? 'ALTERNATIVE' : 'INCOMPLETE',
      candidate_id: recommended ? 'candidate.purchase.base' : null,
      reason_codes: recommended ? [] : ready ? ['not-selected-by-server-ranking'] : ['procurement-not-ready'],
    },
    expenses: [
      { line_id: 'equipment', label: 'Оборудование', amount: acquisition === 'PURCHASE' ? '15000000.00' : null, status: acquisition === 'PURCHASE' ? 'COMPLETE' : 'NOT_APPLICABLE', source_ref: 'financial.capex-equipment' },
      { line_id: 'service', label: acquisition === 'PURCHASE' ? 'Сервис' : 'RaaS payment', amount: acquisition === 'PURCHASE' ? '900000.00' : '10800000.00', status: 'COMPLETE', source_ref: 'financial.annual-service' },
      { line_id: 'roles', label: 'Object FOT', amount: complete ? '18748800.00' : null, status: complete ? 'COMPLETE' : 'INCOMPLETE', source_ref: 'allocation.object-fot' },
    ],
    assumptions: [
      { assumption_id: 'discount', label: 'Discount rate', value: '0.15', unit: '1', provenance_ref: 'finance.discount.default-rate' },
      { assumption_id: 'uncertainty', label: 'Uncertainty profile', value: uncertainty, unit: 'profile', provenance_ref: `scenario.${uncertainty.toLowerCase()}` },
    ],
    source_refs: ['R03:F23-F32', `run.${acquisition.toLowerCase()}.${uncertainty.toLowerCase()}`],
  };
}

const variants = ['EQUIPMENT_PRICE', 'OPERATION_VOLUME', 'ROLE_SALARY'].flatMap((parameter) => (
  ['LOWER', 'UPPER'].map((direction) => ({
    variant_id: `variant.${parameter.toLowerCase()}.${direction.toLowerCase()}`,
    override: { parameter_id: parameter, direction },
    status: 'COMPLETE',
    npv_project: {
      delta_value: direction === 'LOWER' ? '1000000.00' : '-1000000.00',
      unit: 'RUB',
    },
    step_reasons: parameter === 'OPERATION_VOLUME' && direction === 'UPPER'
      ? ['discrete-fleet-step', 'no-headcount-step']
      : ['no-discrete-fleet-step', 'no-headcount-step'],
  }))
));

const bundle = {
  schema_version: 'commercial-scenarios-bundle-v2',
  run_id: 'run.c21.golden',
  project_id: projectId,
  tenant_id: tenantId,
  input_revision: revision,
  roles: [
    { role_id: 'role.operator', role_code: 'warehouse_operator', headcount: '20', monthly_gross_salary: { status: 'KNOWN', value: '100000', unit: 'RUB/person/month', source: 'USER', provenance_ref: 'input.salary.operator' } },
    { role_id: 'role.tech', role_code: 'tech_support', headcount: '1', monthly_gross_salary: { status: 'MISSING', value: null, unit: 'RUB/person/month', source: null, provenance_ref: null } },
  ],
  scenarios: ['PURCHASE', 'RAAS'].flatMap((acquisition) => (
    ['PESSIMISTIC', 'BASE', 'OPTIMISTIC'].map((uncertainty) => scenario(acquisition, uncertainty))
  )),
  sensitivity: {
    source_schema_version: 'sensitivity-result-v1', source_digest: `sha256:${'7'.repeat(64)}`, project_id: projectId, tenant_id: tenantId, variants,
  },
  ranking: {
    source_schema_version: 'ranking-result-v2', source_digest: `sha256:${'8'.repeat(64)}`,
    technical_recommendation: { status: 'RECOMMENDED', candidate_id: 'candidate.purchase.base', reason_codes: [] },
    financial_recommendation: { status: 'RECOMMENDED', candidate_id: 'candidate.purchase.base', reason_codes: [] },
  },
  versions: {
    procurement: 'procurement-report-v1', finance_purchase: 'financial-result-v1',
    finance_raas: 'raas-financial-result-v1', allocation: 'multiprocess-allocation-result-v1',
    ranking: 'ranking-result-v2', sensitivity: 'sensitivity-result-v1',
  },
  limitations: [
    'Это расчётный сценарий, не коммерческое предложение.',
    'VAT rate не выводится из gross price.',
    'Simulation и procurement actions не выполняются в C21.',
  ],
};

const string = { type: 'string', minLength: 1 };
const nullableString = { type: ['string', 'null'] };
const digest = { type: 'string', pattern: '^sha256:[0-9a-f]{64}$' };
const closed = (properties, required = Object.keys(properties)) => ({
  type: 'object', additionalProperties: false, required, properties,
});
const schema = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'commercial-scenarios-bundle-v2.schema.json',
  title: 'CommercialScenariosBundleV2',
  ...closed({
    schema_version: { const: 'commercial-scenarios-bundle-v2' }, run_id: string,
    project_id: string, tenant_id: string, input_revision: string,
    roles: { type: 'array', minItems: 1, items: { $ref: '#/$defs/role' } },
    scenarios: { type: 'array', minItems: 6, maxItems: 6, items: { $ref: '#/$defs/scenario' } },
    sensitivity: { $ref: '#/$defs/sensitivity' }, ranking: { $ref: '#/$defs/ranking' },
    versions: { type: 'object', additionalProperties: { type: 'string' }, minProperties: 1 },
    limitations: { type: 'array', items: { type: 'string' } },
  }),
  $defs: {
    salary: closed({ status: { enum: ['KNOWN', 'MISSING'] }, value: nullableString, unit: { const: 'RUB/person/month' }, source: nullableString, provenance_ref: nullableString }),
    role: closed({ role_id: string, role_code: string, headcount: { type: 'string', pattern: '^[0-9]+$' }, monthly_gross_salary: { $ref: '#/$defs/salary' } }),
    metric: closed({ status: { enum: ['COMPLETE', 'NOT_REACHED', 'N_A', 'INCOMPLETE'] }, value: nullableString, unit: { enum: ['RUB', 'YEAR', 'PERCENT'] } }),
    rawSource: closed({ source_id: string }),
    rawMoney: closed({ raw_amount: string, currency: string, tax_basis: string, vat_rate: nullableString, source: { $ref: '#/$defs/rawSource' } }),
    money: closed({ status: string, cash_gross_rub: nullableString, raw_money: { $ref: '#/$defs/rawMoney' } }),
    procurement: closed({
      source_schema_version: { const: 'procurement-report-v1' }, source_digest: digest,
      acquisition: { enum: ['PURCHASE', 'RAAS'] }, procurement_status: string,
      procurement_ready: { type: 'boolean' }, blockers: { type: 'array', items: string },
      supply_risk: string, money: { $ref: '#/$defs/money' },
    }),
    ledger: closed({
      year: { type: 'integer', minimum: 1, maximum: 15 }, primary_cf_base: nullableString,
      primary_cf_scenario: nullableString, differential_cf: nullableString,
      status: { enum: ['COMPLETE', 'INCOMPLETE'] }, source_refs: { type: 'array', items: string },
    }),
    financial: closed({
      source_schema_version: { enum: ['financial-result-v1', 'raas-financial-result-v1'] }, source_digest: digest,
      project_id: string, tenant_id: string, input_revision: string,
      status: { enum: ['COMPLETE', 'INCOMPLETE'] }, npv_project: { $ref: '#/$defs/metric' },
      simple_payback: { $ref: '#/$defs/metric' }, discounted_payback: { $ref: '#/$defs/metric' },
      annual_ledgers: { type: 'array', minItems: 5, items: { $ref: '#/$defs/ledger' } },
    }),
    roleConservation: closed({ role_id: string, headcount: { type: 'integer', minimum: 0 }, released: { type: 'integer', minimum: 0 }, remaining: { type: 'integer', minimum: 0 } }),
    allocation: closed({
      source_schema_version: { const: 'multiprocess-allocation-result-v1' }, source_digest: digest,
      project_id: string, tenant_id: string, input_revision: string,
      role_conservation: { type: 'array', items: { $ref: '#/$defs/roleConservation' } },
      control_required_once: { type: 'integer', minimum: 0 }, technicians_required_once: { type: 'integer', minimum: 0 },
    }),
    recommendation: closed({ status: string, candidate_id: nullableString, reason_codes: { type: 'array', items: string } }),
    expense: closed({ line_id: string, label: string, amount: nullableString, status: string, source_ref: string }),
    assumption: closed({ assumption_id: string, label: string, value: string, unit: string, provenance_ref: string }),
    scenario: closed({
      scenario_id: string, acquisition: { enum: ['PURCHASE', 'RAAS'] },
      uncertainty: { enum: ['PESSIMISTIC', 'BASE', 'OPTIMISTIC'] },
      procurement: { $ref: '#/$defs/procurement' }, financial: { $ref: '#/$defs/financial' },
      allocation: { $ref: '#/$defs/allocation' }, recommendation: { $ref: '#/$defs/recommendation' },
      expenses: { type: 'array', items: { $ref: '#/$defs/expense' } },
      assumptions: { type: 'array', items: { $ref: '#/$defs/assumption' } },
      source_refs: { type: 'array', items: string },
    }),
    override: closed({ parameter_id: { enum: ['EQUIPMENT_PRICE', 'OPERATION_VOLUME', 'ROLE_SALARY'] }, direction: { enum: ['LOWER', 'UPPER'] } }),
    sensitivityDelta: closed({ delta_value: nullableString, unit: { const: 'RUB' } }),
    sensitivityVariant: closed({
      variant_id: string, override: { $ref: '#/$defs/override' }, status: { enum: ['COMPLETE', 'BLOCKED'] },
      npv_project: { $ref: '#/$defs/sensitivityDelta' }, step_reasons: { type: 'array', items: string },
    }),
    sensitivity: closed({
      source_schema_version: { const: 'sensitivity-result-v1' }, source_digest: digest,
      project_id: string, tenant_id: string,
      variants: { type: 'array', minItems: 6, maxItems: 6, items: { $ref: '#/$defs/sensitivityVariant' } },
    }),
    recommendationSummary: closed({ status: string, candidate_id: nullableString, reason_codes: { type: 'array', items: string } }),
    ranking: closed({
      source_schema_version: { const: 'ranking-result-v2' }, source_digest: digest,
      technical_recommendation: { $ref: '#/$defs/recommendationSummary' },
      financial_recommendation: { $ref: '#/$defs/recommendationSummary' },
    }),
  },
};

const encoded = (value) => `${JSON.stringify(value, null, 2)}\n`;
const outputs = new Map([
  [path.join(root, 'frontend/tests/fixtures/commercial-scenarios-v2.golden.json'), encoded(bundle)],
  [path.join(root, 'contracts/commercial-scenarios-bundle-v2.schema.json'), encoded(schema)],
]);
if (process.argv.includes('--check')) {
  const drift = [];
  for (const [file, content] of outputs) {
    try {
      if (await readFile(file, 'utf8') !== content) drift.push(path.relative(root, file));
    } catch {
      drift.push(path.relative(root, file));
    }
  }
  if (drift.length) throw new Error(`C21 contract drift: ${drift.join(', ')}`);
} else {
  await mkdir(path.join(root, 'frontend/tests/fixtures'), { recursive: true });
  for (const [file, content] of outputs) await writeFile(file, content);
}
