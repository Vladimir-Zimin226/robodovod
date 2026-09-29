import { useEffect, useRef, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import { SCENARIO_CONTROLS, SCENARIO_METRICS, canonicalJson, editScenarioInput, inputDigest, metricText, scenarioInputError } from '../projectScenarioModel';
import { decimalDifference } from '../displayNumber';
import { presentationValue, sourceLabel, unitLabel } from '../presentation';

const API = import.meta.env.VITE_API_URL || '';
const names = { PURCHASE: 'Покупка', RAAS: 'RaaS', BASELINE: 'Без роботов' };
const profiles = { BASE: 'Базовый', PESSIMISTIC: 'Пессимистичный', OPTIMISTIC: 'Оптимистичный' };
const money = raw => raw == null ? 'Нет данных' : presentationValue('', raw, 'RUB');

async function request(url, body, signal) {
  const response = await fetch(url, { method: 'POST', credentials: 'include', signal,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) {
    console.error('Economics request:', response.status, data);
    throw new Error('Не удалось проверить или сохранить новый расчёт. Проверьте входы и соединение, затем повторите попытку.');
  }
  return data;
}

export default function ProjectScenarioDialog({ project, run, onComplete, onClose, onPhysical }) {
  const original = run.input_snapshot.economics;
  const [draft, setDraft] = useState(() => structuredClone(original));
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState('changed');
  const [error, setError] = useState('');
  const dialog = useRef(null);
  const revision = useRef(0);
  const saving = useRef(false);
  const saveAttempt = useRef(null);
  const saveController = useRef(null);
  const alive = useRef(false);
  const changed = canonicalJson(original) !== canonicalJson(draft);
  const validationError = scenarioInputError(draft);
  const source = { scenario_id: run.scenario_id, source_run_id: run.id, expected_result_sha256: run.result_sha256,
    capacity_run_id: run.input_snapshot.capacity_run_id };

  useEffect(() => {
    alive.current = true;
    dialog.current.showModal();
    return () => { alive.current = false; saveController.current?.abort(); };
  }, []);

  useEffect(() => {
    if (validationError) return undefined;
    const controller = new AbortController();
    const currentRevision = revision.current;
    let requestTimer;
    const debounce = setTimeout(async () => {
      setState('calculating'); setError('');
      requestTimer = setTimeout(() => controller.abort(), 60000);
      try {
        const data = await request(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs/preview`, {
          scenario_id: run.scenario_id, source_run_id: run.id, expected_result_sha256: run.result_sha256,
          capacity_run_id: run.input_snapshot.capacity_run_id, input: draft }, controller.signal);
        const digest = await inputDigest(draft);
        if (controller.signal.aborted || currentRevision !== revision.current) return;
        if (data.source_run_id !== run.id || data.source_result_sha256 !== run.result_sha256
          || data.capacity_run_id !== run.input_snapshot.capacity_run_id || data.input_sha256 !== digest) throw new Error('Предпросмотр относится к другому вводу или версии.');
        setPreview({ ...data, draftJson: canonicalJson(draft), revision: currentRevision });
        setState(data.result?.issues?.length || data.result?.scenarios?.length !== 6 ? 'partial' : 'ready');
      } catch (reason) {
        if (alive.current && currentRevision === revision.current) { setError(reason.name === 'AbortError' ? 'Истекло время предпросмотра. Повторите пересчёт.' : reason.message); setState('error'); }
      } finally { clearTimeout(requestTimer); }
    }, 350);
    return () => { clearTimeout(debounce); clearTimeout(requestTimer); controller.abort(); };
  }, [draft, project.id, run.id, run.result_sha256, run.scenario_id, run.input_snapshot.capacity_run_id, validationError]);

  const edit = (field, value) => {
    if (saving.current) return;
    revision.current += 1; setPreview(null); setState('changed'); setError('');
    saveAttempt.current = null;
    setDraft(input => editScenarioInput(input, field, value));
  };
  const reset = () => {
    if (saving.current) return;
    revision.current += 1; saveAttempt.current = null; setDraft(structuredClone(original)); setPreview(null); setError(''); setState('changed');
  };
  const save = async () => {
    if (saving.current || !preview || !changed || validationError || preview.revision !== revision.current || preview.draftJson !== canonicalJson(draft)) return;
    saving.current = true; setState('saving'); setError('');
    const input = structuredClone(draft);
    const controller = new AbortController(); saveController.current = controller;
    const timer = setTimeout(() => controller.abort(), 70000);
    saveAttempt.current ||= { key: crypto.randomUUID(), inputJson: canonicalJson(input) };
    try {
      const saved = await request(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs`, {
        ...source, input, preview_input_sha256: preview.input_sha256, idempotency_key: saveAttempt.current.key }, controller.signal);
      if (!alive.current) return;
      onComplete?.(saved); onClose();
    } catch (reason) {
      if (alive.current) { setError(`${reason.name === 'AbortError' ? 'Истекло время сохранения' : reason.message}. Повтор использует тот же ключ версии.`); setState('error'); }
    } finally { clearTimeout(timer); saving.current = false; }
  };
  const result = preview?.result;
  const rows = result?.comparison?.scenarios || [];
  const baseRows = run.result_snapshot?.comparison?.scenarios || [];
  const physical = result?.staffing_preview || run.result_snapshot?.staffing_preview;
  return <dialog ref={dialog} className="project-scenario-dialog" aria-label="Сценарии и пересчёт" onCancel={event => { event.preventDefault(); if (!saving.current) onClose(); }}>
    <header><div><h2>Сценарии и пересчёт</h2><p>{project.name} · операция сохранённого расчёта · версия {run.id}</p></div><button disabled={state === 'saving'} onClick={onClose} aria-label="Закрыть сценарии">Закрыть</button></header>
    <p>Меняются финансовые вводные. Объём, маршрут, график, доступность и парк взяты из сохранённой физической версии.</p>
    {onPhysical && <button disabled={state === 'saving'} onClick={() => { onClose(); onPhysical(); }}>Изменить физические вводные</button>}
    <div className="project-scenario-columns"><fieldset disabled={state === 'saving'}>
      {[...new Set(SCENARIO_CONTROLS.map(([group]) => group))].map(group => <section key={group}><h3>{group}</h3>
        {group === 'Коммерческие условия' && <><label>Внедрение<select aria-label="Режим внедрения" value={draft.implementation_mode || 'FIXED'} onChange={event => edit('implementation_mode', event.target.value)}><option value="FIXED">Сумма в рублях</option><option value="PERCENT">% цены парка</option></select></label>
          <label>RaaS<select aria-label="Режим RaaS" value={draft.raas_mode || 'FIXED'} onChange={event => edit('raas_mode', event.target.value)}><option value="FIXED">₽/робот/месяц</option><option value="PERCENT">% цены одного робота в месяц</option></select></label></>}
        {SCENARIO_CONTROLS.filter(([g, field]) => g === group
          && (field !== 'implementation_percent' || draft.implementation_mode === 'PERCENT')
          && (field !== 'implementation_cost_total_gross' || draft.implementation_mode !== 'PERCENT')
          && (field !== 'raas_percent_monthly' || draft.raas_mode === 'PERCENT')
          && (field !== 'raas_monthly_per_robot_gross' || draft.raas_mode !== 'PERCENT')).map(([, field, label, min, max, step, sliderMax]) => <label key={field}>{label}
            <input aria-label={`${label}: ползунок`} type="range" min={min} max={Math.max(sliderMax, Number(draft[field]) || 0)} step={step} disabled={draft[field] == null || draft[field] === ''} value={draft[field] ?? min} onChange={event => edit(field, event.target.value)} />
            <input aria-label={label} type="number" min={min} max={max ?? undefined} step={['horizon_years', 'raas_contract_months'].includes(field) ? 1 : 'any'} value={draft[field] ?? ''} onChange={event => edit(field, event.target.value)} />
            <small>Источник: {sourceLabel({ source: draft.field_sources?.[field] })} · исходное: {presentationValue(field, original[field])}{String(draft[field] ?? '') !== String(original[field] ?? '') ? ' · изменено' : ''}</small>
            {field === 'manual_units_per_shift' && <small>Выработка выбранной роли · {unitLabel(run.result_snapshot?.comparison?.inputs?.manual_productivity?.unit) || 'ед./человек/смену'}</small>}
          </label>)}
      </section>)}
    </fieldset><section className="project-scenario-results" aria-live="polite">
      <p role="status">{{ changed: 'Ввод изменён', calculating: 'Пересчитываем…', ready: 'Предпросмотр готов', partial: 'Не хватает данных', error: 'Ошибка', saving: 'Сохраняем новую версию…' }[state]}</p>
      {(error || validationError) && <p role="alert">{validationError || error}</p>}
      {(result?.issues || []).map((issue, index) => <p key={index}>{issue.message} {issue.next_step}</p>)}
      {Object.entries(result?.branches || {}).filter(([, branch]) => branch.required_fields?.length).map(([key, branch]) => <p key={key}>Не хватает условий для {names[key.toUpperCase()] || key}: {branch.required_fields.join(', ')}.</p>)}
      {preview?.physical && <p>Операция: {preview.physical.process?.process_code}. Парк: {preview.physical.capacity?.value?.selected_fleet ?? 'неизвестно'}; покрытие нагрузки: {preview.physical.capacity?.value?.coverage?.value ?? 'неизвестно'} {preview.physical.capacity?.value?.coverage?.unit || ''}. Физическая версия: {preview.physical.capacity_run_id}.</p>}
      {result?.monetary_input_basis && <p>Денежная база: робот {money(result.monetary_input_basis.unit_price_gross_rub)}; парк {result.monetary_input_basis.fleet}. Внедрение: {money(result.monetary_input_basis.implementation?.amount_gross_rub)}; RaaS: {money(result.monetary_input_basis.raas?.per_robot_month_gross_rub)} на робота в месяц.</p>}
      {physical && <p>Люди по сохранённой физике и текущей экономике: {Object.entries(physical).map(([kind, data]) => `${names[kind]}: высвобождение ${data.released ?? 'неизвестно'}, диспетчеры ${data.control_required ?? 'неизвестно'}, техники ${data.technicians_required ?? 'неизвестно'}`).join('; ')}.</p>}
      <div className="commercial-table-wrap"><table aria-label="Исходный вариант и предпросмотр"><thead><tr><th>Вариант</th><th>Показатель</th><th>Исходный</th><th>Предпросмотр</th><th>Разница</th></tr></thead><tbody>
        {['PURCHASE', 'RAAS'].flatMap(kind => SCENARIO_METRICS.map(([key, label]) => {
          const before = baseRows.find(row => row.acquisition === kind && row.uncertainty === 'BASE')?.metrics?.[key];
          const after = rows.find(row => row.acquisition === kind && row.uncertainty === 'BASE')?.metrics?.[key];
          const delta = before?.status === 'COMPLETE' && after?.status === 'COMPLETE' ? metricText({ ...after, value: decimalDifference(after.value, before.value) }) : 'Нет данных';
          return <tr key={`${kind}:${key}`}><th>{names[kind]}</th><td>{label}</td><td>{metricText(before)}</td><td>{metricText(after)}</td><td>{delta}</td></tr>;
        }))}</tbody></table></div>
      <p>Затраты без роботов за год 1 — {metricText((result?.comparison || run.result_snapshot?.comparison)?.baseline?.metrics?.opex_year_1)}.</p>
      <div className="commercial-table-wrap"><table aria-label="Шесть финансовых сценариев"><thead><tr><th>Вариант</th>{SCENARIO_METRICS.map(([key, label]) => <th key={key}>{label}</th>)}</tr></thead><tbody>
        {['PURCHASE', 'RAAS'].flatMap(kind => ['PESSIMISTIC', 'BASE', 'OPTIMISTIC'].map(profile => { const row = rows.find(item => item.acquisition === kind && item.uncertainty === profile);
          return <tr key={`${kind}:${profile}`}><th>{names[kind]} · {profiles[profile]}</th>{SCENARIO_METRICS.map(([key]) => <td key={key}>{metricText(row?.metrics?.[key])}</td>)}</tr>; }))}
      </tbody></table></div>
      <ScenarioChart charts={preview?.charts} metric="cashflow" label="Денежные потоки по годам" />
      <ScenarioChart charts={preview?.charts} metric="cumulative_effect" label="Накопленный эффект с учётом CAPEX" />
      <p>Состав договора, политика обслуживания, остаточные операции и подтверждения сохранены из исходной версии. Включённые расходы определяет серверный расчёт по этим условиям.</p>
    </section></div>
    <footer><button disabled={state === 'saving'} onClick={reset}>Вернуть исходные значения</button><button disabled={state === 'saving'} onClick={() => { revision.current += 1; setDraft(current => ({ ...current })); setPreview(null); }}>Повторить предпросмотр</button>
      <button className="primary-action" disabled={!changed || !preview || Boolean(validationError) || state === 'saving' || state === 'calculating'} onClick={save}>Сохранить и пересчитать</button><button disabled={state === 'saving'} onClick={onClose}>Отмена</button></footer>
  </dialog>;
}

function ScenarioChart({ charts, metric, label }) {
  const series = (charts?.series || []).filter(row => row.scenario_id.includes('.base') && row.points.some(point => point[metric] != null));
  if (!series.length) return <p>{label}: ряд недоступен.</p>;
  const values = series.flatMap(row => row.points.map(point => Number(point[metric])).filter(Number.isFinite));
  const min = Math.min(0, ...values), max = Math.max(0, ...values), span = max - min || 1;
  const years = Math.max(1, ...series.flatMap(row => row.points.map(point => point.year)));
  const colors = ['#a3e635', '#67e8f9', '#fbbf24'];
  return <figure className="project-scenario-chart"><figcaption>{label} · млн ₽ · год 0 — вложения</figcaption>
    <svg viewBox="0 0 640 250" role="img" aria-label={label}><text x="4" y="16">{(max / 1e6).toFixed(2)}</text><text x="4" y="225">{(min / 1e6).toFixed(2)}</text>
      <line x1="70" x2="620" y1={25 + max / span * 190} y2={25 + max / span * 190} stroke="#64748b" />
      {series.map((row, index) => <polyline key={row.scenario_id} fill="none" stroke={colors[index]} strokeWidth="2" points={row.points.filter(point => point[metric] != null).map(point => `${70 + point.year / years * 550},${25 + (max - Number(point[metric])) / span * 190}`).join(' ')} />)}
      {Array.from({ length: years + 1 }, (_, year) => <text key={year} x={70 + year / years * 550} y="244" textAnchor="middle">{year}</text>)}
    </svg><p>{series.map((row, index) => <span key={row.scenario_id} style={{ color: colors[index], marginRight: 16 }}>{row.scenario_id.includes('purchase') ? 'Покупка' : row.scenario_id.includes('raas') ? 'RaaS' : 'Без роботов'}</span>)}</p>
    <details><summary>Значения ряда и основание</summary><p>Сохранённые денежные потоки; год 0 содержит первоначальные вложения.</p><table><tbody>{series.flatMap(row => row.points.map(point => <tr key={`${row.scenario_id}:${point.year}`}><th>{row.scenario_id.includes('purchase') ? 'Покупка' : row.scenario_id.includes('raas') ? 'Аренда' : 'Без роботов'} · год {point.year}</th><td>{money(point[metric])}</td></tr>))}</tbody></table></details>
  </figure>;
}
