import { useEffect, useState } from 'react';
import { physicalRunOption } from '../physicalScenario';

export default function SavedPhysicalScenarios({ request, analysisRunId, children }) {
  const [options, setOptions] = useState([]);
  const [selected, setSelected] = useState(analysisRunId);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const get = async (path) => {
      const response = await fetch(`${import.meta.env.VITE_API_URL || ''}${path}`, { credentials: 'include', signal: controller.signal });
      if (!response.ok) throw new Error(`Не удалось открыть физические сценарии: HTTP ${response.status}`);
      return response.json();
    };
    const base = `/api/projects/${encodeURIComponent(request.project_id)}/analysis-runs`;
    get(base).then(async ({ items }) => {
      const runs = await Promise.all(items.filter((item) => item.run_kind === 'FULL_ANALYSIS' && item.status === 'SUCCEEDED')
        .map((item) => get(`${base}/${encodeURIComponent(item.id)}`)));
      if (!controller.signal.aborted) setOptions(runs.map(physicalRunOption).filter((item) => item
        && item.request.project_id === request.project_id && item.request.tenant_id === request.tenant_id));
    }).catch((failure) => { if (failure.name !== 'AbortError') setError(failure.message); });
    return () => controller.abort();
  }, [request.project_id, request.tenant_id]);
  const active = options.find((item) => item.id === selected);
  return <>
    <div className="simulation-physical-selector panel">
      <label>Физический сценарий проекта<select aria-label="Физический сценарий проекта" value={selected} onChange={(event) => setSelected(event.target.value)}>
        {!options.some((item) => item.id === analysisRunId) && <option value={analysisRunId}>Текущий сохранённый расчёт</option>}
        {options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select></label>
      <p>Выбор открывает техническую основу сохранённой версии. Изменение спроса, маршрута, парка или графика требует нового расчёта.</p>
      {error && <p role="alert">{error}</p>}
    </div>
    {children(active?.request || request, active?.id || analysisRunId)}
  </>;
}
