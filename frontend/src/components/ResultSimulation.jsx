import { isCapacityAnalysisResponse } from '../capacityResultsModel';
import { isCommercialScenariosBundle } from '../commercialScenariosModel';
import { commercialSimulationSource, linkedTechnicalRun, resultCapacityRunId } from '../resultSimulationModel';
import Simulation2DReport from './Simulation2DReport';
import TechnicalVisualization from './TechnicalVisualization';
import CinematicScene from './CinematicScene';
import { formatServerMoney } from '../commercialScenariosModel';

export default function ResultSimulation({ result, run, technicalRun, capacityRequest, project, onReady }) {
  const capacityRunId = resultCapacityRunId(result, run);
  const linkedTechnical = linkedTechnicalRun(technicalRun, capacityRunId, project?.id);
  if (isCapacityAnalysisResponse(result)) return <TechnicalVisualization
    run={run} capacityRequest={capacityRequest} capacityRunId={capacityRunId} project={project} autoStart onReady={onReady} />;
  if (result?.schema_version === 'economics-partial-result-v1') return <TechnicalVisualization run={linkedTechnical || run} />;
  if (isCommercialScenariosBundle(result)) {
    const source = commercialSimulationSource(result, run, technicalRun, project?.id);
    if (source?.kind === 'TECHNICAL') return <TechnicalVisualization run={source.run} />;
    const basePurchase = result.scenarios?.find(item => item.acquisition === 'PURCHASE' && item.uncertainty === 'BASE');
    return source?.kind === 'ECONOMICS' ? <div className="result-simulation visualization-wide mx-auto my-6"><CinematicScene
      fleet={result.monetary_input_basis?.fleet ?? null} queue={null}
      npv={formatServerMoney(basePurchase?.report_facts?.project_npv?.value)} resultDigest={result.run_id}>
      <Simulation2DReport request={source.request} analysisRunId={result.run_id} />
    </CinematicScene></div> : null;
  }
  return null;
}
