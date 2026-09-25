import { useEffect, useState } from 'react';
import EconomicsInputsV2 from './EconomicsInputsV2';
import { economicsFieldLabel } from '../economicsFieldLabels';

const API = import.meta.env.VITE_API_URL || '';

export default function SavedEconomicsEditor({ project, run, onComplete }) {
  const [capacityRequest, setCapacityRequest] = useState(null);
  const [error, setError] = useState('');
  const capacityRunId = run?.input_snapshot?.capacity_run_id;
  const initialInput = run?.input_snapshot?.economics;
  const confirmedAssumptions = Object.entries(initialInput?.assumption_evidence || {}).filter(([, item]) => item?.confirmed);

  useEffect(() => {
    if (!project?.id || !capacityRunId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(capacityRunId)}`, {
      credentials: 'include', signal: controller.signal,
    }).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Расчёт парка недоступен: HTTP ${response.status}`)))
      .then((source) => {
        if (source.run_kind !== 'CAPACITY_ANALYSIS' || source.id !== capacityRunId || !source.input_snapshot) {
          throw new Error('Исходный расчёт парка не соответствует экономическому результату.');
        }
        setCapacityRequest(source.input_snapshot);
      })
      .catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, [project?.id, capacityRunId]);

  if (!capacityRunId || !['economics-explicit-inputs-v2', 'economics-explicit-inputs-v3', 'economics-explicit-inputs-v4'].includes(initialInput?.schema_version)) return null;
  return <details className="mx-auto my-6 max-w-6xl rounded-xl border p-4">
    <summary className="cursor-pointer font-semibold">Изменить допущение и создать новый расчёт</summary>
    <p className="text-sm mt-2">Исходный расчёт останется доступен для повторного открытия.</p>
    <details><summary>Технические подробности</summary><p>Идентификатор исходного расчёта: {run.id}</p></details>
    {confirmedAssumptions.length > 0 && <section className="mt-3 rounded-lg bg-amber-50 p-3 text-sm" aria-label="Подтверждённые допущения сохранённого расчёта">
      <h3 className="font-semibold">Подтверждённые допущения этого расчёта</h3>
      <ul>{confirmedAssumptions.map(([field, item]) => <li key={field}>{economicsFieldLabel(field)}: {item.confirmed_value} · {item.published_on}. {item.rationale}<details><summary>Технические подробности</summary>{item.template_id || 'изменено пользователем'}</details></li>)}</ul>
    </section>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!capacityRequest && !error && <p>Загружаем проверенный расчёт парка…</p>}
    {capacityRequest && <EconomicsInputsV2 key={run.id} capacityRequest={capacityRequest}
      capacityRunId={capacityRunId} project={project} initialInput={initialInput}
      savedResult={run.result_snapshot} sourceRunId={run.id} onComplete={onComplete} />}
  </details>;
}
