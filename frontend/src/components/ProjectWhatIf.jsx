import { useEffect, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import { formatServerMoney } from '../commercialScenariosModel';

const API = import.meta.env.VITE_API_URL || '';
const CONTROLS = [
  ['raas_monthly_per_robot_gross', 'RaaS, ₽/робот/месяц', 0, 1000000],
  ['purchase_price_override_gross', 'Цена робота, ₽', 0, 100000000],
  ['implementation_cost_total_gross', 'Внедрение, ₽', 0, 100000000],
  ['control_monthly_gross', 'Зарплата диспетчера gross, ₽/мес.', 0, 1000000],
  ['manual_units_per_shift', 'Ручная выработка, ед./смену', 1, 100000],
  ['horizon_years', 'Горизонт, лет', 5, 15],
];

export default function ProjectWhatIf({ project, run, onComplete }) {
  const original = run?.input_snapshot?.economics;
  const [draft, setDraft] = useState(() => ({ ...original }));
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState('idle');
  const [error, setError] = useState('');
  const changes = CONTROLS.filter(([field]) => String(draft?.[field] ?? '') !== String(original?.[field] ?? ''));
  useEffect(() => {
    if (!changes.length || !project?.id || !run?.id || original?.schema_version !== 'economics-explicit-inputs-v6') {
      return undefined;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      setState('calculating'); setError('');
      fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs/preview`, {
        method: 'POST', credentials: 'include', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ scenario_id: run.scenario_id, source_run_id: run.id,
          expected_result_sha256: run.result_sha256, capacity_run_id: run.input_snapshot.capacity_run_id,
          input: draft }),
      }).then(async (response) => {
        if (!response.ok) throw new Error(`Предпросмотр: HTTP ${response.status}`);
        return response.json();
      }).then((data) => {
        if (data.source_run_id !== run.id || data.source_result_sha256 !== run.result_sha256) throw new Error('Версия результата изменилась.');
        setPreview(data); setState('ready');
      }).catch((reason) => { if (reason.name !== 'AbortError') { setError(reason.message); setState('error'); } });
    }, 350);
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [draft, project?.id, run?.id, run?.result_sha256, run?.scenario_id, run?.input_snapshot?.capacity_run_id, original?.schema_version, changes.length]);
  if (original?.schema_version !== 'economics-explicit-inputs-v6') return null;
  const base = run?.result_snapshot?.scenarios?.find((row) => row.scenario_id === 'scenario.purchase.base');
  const changed = preview?.result?.scenarios?.find((row) => row.scenario_id === 'scenario.purchase.base');
  const oldMetrics = run?.result_snapshot?.comparison?.scenarios?.find((row) => row.scenario_id === 'scenario.purchase.base')?.metrics;
  const newMetrics = preview?.result?.comparison?.scenarios?.find((row) => row.scenario_id === 'scenario.purchase.base')?.metrics;
  const set = (field, value) => { setPreview(null); setState('idle'); setDraft((current) => ({ ...current, [field]: value,
    field_sources: { ...(current.field_sources || {}), [field]: 'USER' },
    assumption_evidence: Object.fromEntries(Object.entries(current.assumption_evidence || {}).filter(([name]) => name !== field)),
    ...(field === 'purchase_price_override_gross' ? { purchase_price_source: 'Авторское what-if допущение пользователя' } : {}),
    ...(field === 'raas_monthly_per_robot_gross' ? { raas_mode: 'FIXED' } : {}),
    ...(field === 'implementation_cost_total_gross' ? { implementation_mode: 'FIXED' } : {}),
  })); };
  const save = async () => {
    setState('saving'); setError('');
    try {
      const response = await fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ scenario_id: run.scenario_id, source_run_id: run.id,
          capacity_run_id: run.input_snapshot.capacity_run_id, input: draft }),
      });
      if (!response.ok) throw new Error(`Сохранение: HTTP ${response.status}`);
      onComplete?.(await response.json());
    } catch (reason) { setError(reason.message); setState('error'); }
  };
  return <details className="mx-auto max-w-6xl rounded-xl border p-4" aria-label="Что, если">
    <summary className="cursor-pointer font-semibold">Что, если · серверный предпросмотр</summary>
    <p>Измените допущения. Предпросмотр не сохраняет расчёт; сохранение создаёт отдельную версию.</p>
    <div className="grid gap-3 md:grid-cols-3">{CONTROLS.map(([field, label, min, max]) => <label key={field}>{label}<input type="range" min={min} max={max} value={draft?.[field] || 0} onChange={(event) => set(field, event.target.value)} /><input type="number" min={min} max={max} value={draft?.[field] ?? ''} onChange={(event) => set(field, event.target.value)} /></label>)}</div>
    {state === 'calculating' && <p role="status">Пересчитываем…</p>}
    {error && <p role="alert">{error}</p>}
    {changes.length > 0 && <p>Изменены: {changes.map(([, label]) => label).join(', ')}.</p>}
    <div className="grid gap-3 md:grid-cols-2"><p>Исходный NPV проекта: {formatServerMoney(base?.report_facts?.project_npv?.value)}</p><p>Новый NPV проекта: {formatServerMoney(changed?.report_facts?.project_npv?.value)}</p>
      <p>Исходный парк: {base?.report_facts?.fleet_count ?? '—'}; новые диспетчеры: {base?.staffing?.control_additional ?? '—'}; техники: {base?.staffing?.technicians_required ?? '—'}</p><p>Новый парк: {changed?.report_facts?.fleet_count ?? '—'}; новые диспетчеры: {changed?.staffing?.control_additional ?? '—'}; техники: {changed?.staffing?.technicians_required ?? '—'}</p>
      {['capex', 'opex_year_1', 'effect_year_1', 'discounted_payback'].map((name) => <div key={name}>{name}: {oldMetrics?.[name]?.value ?? '—'} → {newMetrics?.[name]?.value ?? '—'}</div>)}</div>
    {state === 'ready' && changed && <button type="button" onClick={save}>Сохранить этот вариант</button>}
  </details>;
}
