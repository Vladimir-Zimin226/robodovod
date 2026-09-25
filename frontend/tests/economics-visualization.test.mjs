import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { buildEconomicsSimulationRequest, buildTechnicalSimulationRequest } from '../src/economicsSimulationRequest.js';

const scenarioSpec = JSON.parse(await readFile(new URL('../../contracts/fixtures/scenario-spec-v2.capacity-only-cleaner.golden.json', import.meta.url), 'utf8'));
const bundle = {
  schema_version: 'commercial-scenarios-bundle-v2',
  run_id: '00000000-0000-0000-0000-000000000001',
  project_id: scenarioSpec.analysis.project_id,
  tenant_id: scenarioSpec.analysis.tenant_id,
  input_revision: scenarioSpec.analysis.input_revision,
};

test('economics visualization binds only the same immutable project, tenant and revision', () => {
  const request = buildEconomicsSimulationRequest(bundle, scenarioSpec);
  assert.equal(request.request_id, `simulation.${bundle.run_id}`);
  assert.equal(request.scenario_spec, scenarioSpec);
  assert.equal(request.mode, 'DAILY');
  assert.equal(request.sla, null);
  assert.deepEqual(request.resources, []);
  assert.equal(request.limits.max_jobs_per_day, 10000);
  assert.equal(buildEconomicsSimulationRequest({ ...bundle, tenant_id: 'other' }, scenarioSpec), null);
  assert.equal(buildEconomicsSimulationRequest({ ...bundle, project_id: 'other' }, scenarioSpec), null);
  assert.equal(buildEconomicsSimulationRequest({ ...bundle, input_revision: 'stale' }, scenarioSpec), null);
  assert.equal(buildEconomicsSimulationRequest(bundle, null), null);
});

test('partial technical run builds a saved C23 request only for matching C11 identity', () => {
  const run = { id: '00000000-0000-0000-0000-000000000002', run_kind: 'FULL_ANALYSIS',
    scenario_spec_snapshot: scenarioSpec,
    result_snapshot: { schema_version: 'economics-partial-result-v1',
      capacity_run_id: scenarioSpec.analysis.capacity_run_id,
      project_id: scenarioSpec.analysis.project_id, tenant_id: scenarioSpec.analysis.tenant_id } };
  const request = buildTechnicalSimulationRequest(run);
  assert.equal(request.request_id, `simulation.${run.id}`);
  assert.equal(request.scenario_spec, scenarioSpec);
  assert.equal(buildTechnicalSimulationRequest({ ...run, result_snapshot: { ...run.result_snapshot, capacity_run_id: 'other' } }), null);
  assert.equal(buildTechnicalSimulationRequest({ ...run, scenario_spec_snapshot: { schema_version: 'scenario-spec-partial-v1' } }), null);
});

test('v2 result and economics form use the dark application palette', async () => {
  const css = await readFile(new URL('../src/index.css', import.meta.url), 'utf8');
  const result = await readFile(new URL('../src/components/CapacityResultsTrace.jsx', import.meta.url), 'utf8');
  const form = await readFile(new URL('../src/components/EconomicsInputsV2.jsx', import.meta.url), 'utf8');
  const scenarios = await readFile(new URL('../src/components/CommercialScenariosV2.jsx', import.meta.url), 'utf8');
  assert.match(result, /capacity-results-v2/);
  assert.match(form, /economics-inputs-v2/);
  assert.match(css, /\.capacity-results-v2 \.bg-white[^\n]*background: var\(--bg-panel\)/);
  assert.match(css, /\.economics-inputs-v2 [^\n]*background: var\(--bg-panel\)/);
  assert.match(scenarios, /<Simulation2DReport[^>]*request=\{simulationRequest\}/);
});
