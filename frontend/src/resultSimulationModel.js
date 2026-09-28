import { isCapacityAnalysisResponse } from './capacityResultsModel.js';
import { buildEconomicsSimulationRequest } from './economicsSimulationRequest.js';

export function resultCapacityRunId(result, run) {
  if (isCapacityAnalysisResponse(result)) return run?.id || result.run_id;
  return result?.capacity_run_id || run?.input_snapshot?.capacity_run_id || null;
}

export function linkedTechnicalRun(technicalRun, capacityRunId, projectId) {
  return capacityRunId && projectId && technicalRun?.input_snapshot?.capacity_run_id === capacityRunId
    && technicalRun?.project_id === projectId ? technicalRun : null;
}

export function commercialSimulationSource(result, run, technicalRun, projectId) {
  const linked = linkedTechnicalRun(technicalRun, resultCapacityRunId(result, run), projectId);
  if (linked) return { kind: 'TECHNICAL', run: linked };
  const request = buildEconomicsSimulationRequest(result, run?.scenario_spec_snapshot);
  return request ? { kind: 'ECONOMICS', request } : null;
}
