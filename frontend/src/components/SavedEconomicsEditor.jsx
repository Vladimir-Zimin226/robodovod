import { useEffect, useState } from 'react';
import EconomicsInputsV2 from './EconomicsInputsV2';
import { savedConditions } from '../savedConditions';

const API = import.meta.env.VITE_API_URL || '';

export default function SavedEconomicsEditor({ project, run, onComplete, autoOpen = false }) {
  return <SavedEconomicsSource key={`${project?.id}:${run?.id}`} project={project} run={run} onComplete={onComplete} autoOpen={autoOpen} />;
}

function SavedEconomicsSource({ project, run, onComplete, autoOpen }) {
  const [capacityRequest, setCapacityRequest] = useState(null);
  const [capacityResult, setCapacityResult] = useState(null);
  const [error, setError] = useState('');
  const capacityRunId = run?.input_snapshot?.capacity_run_id;
  const initialInput = run?.input_snapshot?.economics;
  const conditions = savedConditions(initialInput, run?.result_snapshot);

  useEffect(() => {
    if (!project?.id || !capacityRunId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(capacityRunId)}`, {
      credentials: 'include', signal: controller.signal,
    }).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Расчёт парка недоступен: HTTP ${response.status}`)))
      .then((source) => {
        if (controller.signal.aborted) return;
        if (source.run_kind !== 'CAPACITY_ANALYSIS' || source.id !== capacityRunId || !source.input_snapshot) {
          throw new Error('Исходный расчёт парка не соответствует экономическому результату.');
        }
        setCapacityRequest(source.input_snapshot);
        setCapacityResult(source.result_snapshot);
      })
      .catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, [project?.id, capacityRunId]);

  if (!capacityRunId || !['economics-explicit-inputs-v1', 'economics-explicit-inputs-v2', 'economics-explicit-inputs-v3', 'economics-explicit-inputs-v4', 'economics-explicit-inputs-v5', 'economics-explicit-inputs-v6'].includes(initialInput?.schema_version)) return null;
  return <details id="edit-economics-run" open={autoOpen || undefined} className="mx-auto my-6 max-w-6xl rounded-xl border p-4">
    <summary className="cursor-pointer font-semibold">Изменить допущение и создать новый расчёт</summary>
    <p className="text-sm mt-2">Исходный расчёт останется доступен для повторного открытия.</p>
    {conditions.length > 0 && <section className="saved-conditions" aria-label="Условия сохранённого расчёта">
      <h3 className="font-semibold">Условия этого расчёта</h3>
      {conditions.map((group) => <section key={group.label}><h4>{group.label}</h4><dl>
        {group.rows.map((item) => <div key={item.key}><dt>{item.label}</dt><dd><strong>{item.value}</strong>
          <p>{item.explanation}</p><small>{item.source}{item.date ? ` · ${item.date}` : ''} · {item.confirmed ? 'Подтверждено для сценария пользователем' : 'Подтверждение не сохранено'}</small>
        </dd></div>)}
      </dl></section>)}
      <p>Полные основания и технические источники сохранены в архиве ZIP.</p>
    </section>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!capacityRequest && !error && <p>Загружаем проверенный расчёт парка…</p>}
    {capacityRequest && <EconomicsInputsV2 key={run.id} capacityRequest={capacityRequest} capacityResult={capacityResult}
      capacityRunId={capacityRunId} project={project} initialInput={initialInput}
      savedResult={run.result_snapshot} sourceRunId={run.id} onComplete={onComplete} />}
  </details>;
}
