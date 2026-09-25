const LIMITS = Object.freeze({
  max_jobs_per_day: 10000,
  max_fleet: 100,
  max_runtime_seconds: 60,
  progress_event_batch: 1000,
});

export function buildEconomicsSimulationRequest(bundle, scenarioSpec) {
  if (bundle?.schema_version !== 'commercial-scenarios-bundle-v2'
      || scenarioSpec?.schema_version !== 'scenario-spec-v2'
      || !bundle.run_id
      || scenarioSpec.analysis?.project_id !== bundle.project_id
      || scenarioSpec.analysis?.tenant_id !== bundle.tenant_id
      || scenarioSpec.analysis?.input_revision !== bundle.input_revision) return null;

  return {
    schema_version: 'simulation-request-v1',
    request_id: `simulation.${bundle.run_id}`,
    tenant_id: bundle.tenant_id,
    project_id: bundle.project_id,
    scenario_spec: scenarioSpec,
    mode: 'DAILY',
    peak_factor: null,
    sla: null,
    resources: [],
    limits: { ...LIMITS },
  };
}

export function buildTechnicalSimulationRequest(run) {
  const spec = run?.scenario_spec_snapshot;
  const result = run?.result_snapshot;
  if (run?.run_kind !== 'FULL_ANALYSIS' || result?.schema_version !== 'economics-partial-result-v1'
      || spec?.schema_version !== 'scenario-spec-v2' || !run.id
      || spec.analysis?.capacity_run_id !== result.capacity_run_id
      || spec.analysis?.project_id !== result.project_id
      || spec.analysis?.tenant_id !== result.tenant_id) return null;
  return {
    schema_version: 'simulation-request-v1', request_id: `simulation.${run.id}`,
    tenant_id: result.tenant_id, project_id: result.project_id,
    scenario_spec: spec, mode: 'DAILY', peak_factor: null, sla: null,
    resources: [], limits: { ...LIMITS },
  };
}
