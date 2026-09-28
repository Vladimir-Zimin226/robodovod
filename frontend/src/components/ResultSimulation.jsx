import { isCapacityAnalysisResponse } from '../capacityResultsModel';
import { isCommercialScenariosBundle } from '../commercialScenariosModel';
import { commercialSimulationSource, linkedTechnicalRun, resultCapacityRunId } from '../resultSimulationModel';
import Simulation2DReport from './Simulation2DReport';
import TechnicalVisualization from './TechnicalVisualization';

export default function ResultSimulation({ result, run, technicalRun, capacityRequest, project, onReady }) {
  const capacityRunId = resultCapacityRunId(result, run);
  const linkedTechnical = linkedTechnicalRun(technicalRun, capacityRunId, project?.id);
  if (isCapacityAnalysisResponse(result)) return <TechnicalVisualization
    run={run} capacityRequest={capacityRequest} capacityRunId={capacityRunId} project={project} autoStart onReady={onReady} />;
  if (result?.schema_version === 'economics-partial-result-v1') return <TechnicalVisualization run={linkedTechnical || run} />;
  if (isCommercialScenariosBundle(result)) {
    const source = commercialSimulationSource(result, run, technicalRun, project?.id);
    if (source?.kind === 'TECHNICAL') return <TechnicalVisualization run={source.run} />;
    return source?.kind === 'ECONOMICS' ? <div className="result-simulation mx-auto my-6 max-w-6xl"><Simulation2DReport
      request={source.request} analysisRunId={result.run_id} /></div> : null;
  }
  return null;
}
