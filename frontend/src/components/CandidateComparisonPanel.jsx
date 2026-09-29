import { useEffect, useRef, useState } from 'react';
import { objectConstraintLabel } from '../objectConstraintContext';
import { readCsrfCookie } from '../persistenceApi';
import { formatDecimal, formatPercent } from '../displayNumber';
import { humanizePresentation, presentationValue, reasonLabel, savedCalculationLabel, statusLabel } from '../presentation';
import CandidateThumbnail from './CandidateThumbnail';

const API = import.meta.env.VITE_API_URL || '';
const componentText = {
  availability: 'Доступность', integrations: 'Интеграции', aisle_margin: 'Запас по ширине прохода',
  trl: 'Зрелость', payload_margin: 'Запас грузоподъёмности',
};

export default function CandidateComparisonPanel({ project, capacityRunId }) {
  return <CandidateComparisonSource key={`${project?.id}:${capacityRunId}`} project={project} capacityRunId={capacityRunId} />;
}

function CandidateComparisonSource({ project, capacityRunId }) {
  const [options, setOptions] = useState(null);
  const [selected, setSelected] = useState([]);
  const [constraints, setConstraints] = useState({ payload: '', aisle: '', integrations: '', confirmed: false });
  const [financeRuns, setFinanceRuns] = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const sequence = useRef(0);
  const running = useRef(false);
  useEffect(() => () => { sequence.current += 1; }, []);

  useEffect(() => {
    if (!project?.id || !capacityRunId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/candidate-comparisons/projects/${encodeURIComponent(project.id)}/sources/${encodeURIComponent(capacityRunId)}`,
      { credentials: 'include', signal: controller.signal })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
        return body;
      })
      .then((body) => {
        if (controller.signal.aborted) return;
        setOptions(body);
        setSelected([body.source_position_id].filter(Boolean));
      })
      .catch((reason) => { if (reason.name !== 'AbortError') { console.error('Comparison source:', reason); setError('Не удалось загрузить варианты сравнения. Обновите страницу и выберите актуальный расчёт.'); } });
    return () => controller.abort();
  }, [project?.id, capacityRunId]);

  const compare = async () => {
    if (running.current) return;
    running.current = true;
    const revision = ++sequence.current;
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`${API}/api/candidate-comparisons/projects/${encodeURIComponent(project.id)}`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ source_run_id: capacityRunId, position_ids: selected,
          max_payload_kg: constraints.payload || null, min_aisle_width_m: constraints.aisle || null,
          required_integrations: constraints.integrations.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean),
          constraints_confirmed: constraints.confirmed,
          finance_run_ids: Object.fromEntries(Object.entries(financeRuns).filter(([id, value]) => selected.includes(id) && value.trim()).map(([id, value]) => [id, value.trim()])),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
      if (revision === sequence.current) setResult(body);
    } catch (reason) { console.error('Candidate comparison:', reason); if (revision === sequence.current) setError('Сравнение недоступно. Проверьте пригодность моделей и общие условия выбранных финансовых расчётов; повторите запрос.'); }
    finally { running.current = false; setBusy(false); }
  };

  const change = (positionId) => {
    sequence.current += 1;
    setSelected((current) => current.includes(positionId) ? current.filter((id) => id !== positionId)
      : current.length < 3 ? [...current, positionId] : current);
    setResult(null);
  };
  const constraint = (key, value) => { sequence.current += 1; setConstraints((current) => ({ ...current, [key]: value, confirmed: key === 'confirmed' ? value : false })); setResult(null); };
  if (!project?.id || !capacityRunId) return <section className="panel p-4 text-sm" aria-label="Сравнение кандидатов для операции">
    <h2 className="text-lg font-semibold">Сравнить модели для этой операции</h2>
    <p>Сначала сохраните расчёт парка в проекте. Затем проверьте выбранную модель и доступные альтернативы.</p>
  </section>;
  const selectedNames = selected.map((id) => options?.items.find((item) => item.position_id === id)?.name).filter(Boolean);
  const eligibleSelected = selected.filter((id) => { const item = options?.items.find((row) => row.position_id === id);
    return item?.calculation_ready && item?.maturity_status !== 'RND'; });
  const missingFinance = eligibleSelected.filter((id) => !financeRuns[id]);
  return <section className="candidate-comparison panel space-y-3 p-4" aria-label="Сравнение кандидатов для операции">
    <h2 className="text-lg font-semibold">Сравнить модели для этой операции</h2>
    <p className="text-sm">Сохранённый расчёт парка задаёт общие входы. Можно оценить одну модель или добавить ещё 1–2 с тем же физическим профилем. Технический и денежный выводы проверяются отдельно; сохранённые расчёты не меняются.</p>
    {!options && !error && <p role="status" className="text-sm">Загружаем совместимые модели для сохранённого расчёта…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {options && <>
      <p className="text-sm">Сравниваются: {selectedNames.length ? selectedNames.join(' и ') : 'модели ещё не выбраны'}.</p>
      {options.items.length < 2 && <p role="status" className="text-sm text-amber-800">В активном каталоге нет второй модели с тем же расчётным профилем. Оценка единственной позиции остаётся предварительной.</p>}
      <p className="text-xs">В активном каталоге {options.items.length} позиции с тем же физическим профилем.</p>
      <div className="candidate-options">{options.items.map((item) => <label key={item.position_id} className="candidate-option">
        <CandidateThumbnail key={item.media?.url || item.position_id} media={item.media} name={item.name} />
        <input type="checkbox" checked={selected.includes(item.position_id)} disabled={!selected.includes(item.position_id) && selected.length >= 3} onChange={() => change(item.position_id)} />{' '}
        <span><strong>{item.name}</strong><small>{humanizePresentation(item.comparison_note)}</small><small>{statusLabel(item.price_status)}</small></span>
      </label>)}</div>
      {options.object_constraint_context && <p>Сравнение использует подтверждённые ограничения сохранённого расчёта: {Object.entries(options.object_constraint_context).filter(([key, value]) => !['object_kind', 'requirement_sources', 'time_scope'].includes(key) && value !== null && value !== false && (!Array.isArray(value) || value.length > 0)).map(([key, value]) => `${objectConstraintLabel(key)}: ${value === true ? 'да' : value}`).join('; ')}. Для изменения создайте новую физическую версию.</p>}
      <details><summary>Ограничения объекта и финансовые расчёты</summary>
        <p className="text-sm">Ограничения применяются ко всем позициям одинаково. Неизвестный паспорт остаётся неподтверждённым.</p>
        {!options.object_constraint_context && <div className="flex flex-wrap gap-2 text-sm">
          <label>Масса паллеты, кг <input aria-label="Масса паллеты" className="w-24 rounded border p-1" value={constraints.payload} onChange={(e) => constraint('payload', e.target.value)} /></label>
          <label>Доступная ширина прохода, м <input aria-label="Ширина прохода" className="w-24 rounded border p-1" value={constraints.aisle} onChange={(e) => constraint('aisle', e.target.value)} /></label>
          <label>Нужные интеграции, через запятую <input aria-label="Нужные интеграции" className="w-44 rounded border p-1" value={constraints.integrations} onChange={(e) => constraint('integrations', e.target.value)} /></label>
          <label><input type="checkbox" checked={constraints.confirmed} onChange={(e) => constraint('confirmed', e.target.checked)} /> Подтверждаю ограничения</label>
        </div>}
        <p className="mt-2 text-sm">Для денежного сравнения выберите сохранённый полный финансовый расчёт каждой допустимой позиции. Сервер проверит исходный расчёт парка, одинаковые входы и условия. Пустой выбор оставляет денежный вывод недоступным.</p>
        {selected.map((id) => <label key={id} className="mt-1 block text-sm">{options.items.find((item) => item.position_id === id)?.name} — финансовый расчёт{' '}
          <select aria-label={`Финансовый расчёт модели ${options.items.find((item) => item.position_id === id)?.name}`} className="max-w-full rounded border p-1" value={financeRuns[id] || ''} onChange={(e) => { sequence.current += 1; setFinanceRuns((current) => ({ ...current, [id]: e.target.value })); setResult(null); }}>
            <option value="">Не выбран</option>{(options.finance_options || []).filter((item) => item.position_id === id).map((item) => <option key={item.run_id} value={item.run_id}>{savedCalculationLabel(item.created_at)} · NPV {presentationValue('', item.npv_project, 'RUB')} · {item.conditions?.horizon_years ?? 'не указан'} лет · ставка {formatPercent(item.conditions?.discount_rate, 1)}</option>)}
          </select></label>)}
      </details>
      <p role="status" className="text-sm">{selected.length === 0 ? 'Выберите хотя бы одну модель.' : selected.length > eligibleSelected.length ? 'Непроверенная или исследовательская модель останется информационной; технический балл возможен только для расчётных моделей.' : selected.length === 1 ? 'Можно оценить единственную расчётную позицию; сравнительного вывода пока нет.' : 'Можно сравнить технические показатели.'} {missingFinance.length ? `Денежное сравнение недоступно: для ${missingFinance.map((id) => options.items.find((item) => item.position_id === id)?.name).join(', ')} нет выбранного сопоставимого полного финансового расчёта.` : 'Для денежного вывода сервер ещё проверит общие условия финансовых расчётов.'}</p>
      <button type="button" className="primary-action" disabled={busy || selected.length === 0} onClick={compare}>{busy ? 'Оцениваем…' : 'Оценить выбранные позиции'}</button>
    </>}
    {result && <>
      <p className="text-sm">Все модели пересчитаны на входах выбранного сохранённого расчёта.</p>
      {result.role_scope.affected_role_code === 'forklift_driver' && <p className="text-sm text-amber-800">Для паллетной перевозки учитывается только подтверждённый труд водителя погрузчика. Экономия комплектовщиков, сортировщиков и упаковщиков сюда не входит.</p>}
      <p className="text-sm"><strong>Технический вывод:</strong> {humanizePresentation(result.technical_recommendation.reason)}. <strong>Денежный вывод:</strong> {humanizePresentation(result.financial_recommendation.reason)}.</p>
      <div className="overflow-x-auto"><table className="w-full min-w-[780px] border-collapse text-sm"><thead><tr><th className="border p-2">Модель</th><th className="border p-2">Допуск</th><th className="border p-2">Парк</th><th className="border p-2">Технический балл</th><th className="border p-2">NPV</th><th className="border p-2">Денежный балл</th></tr></thead>
        <tbody>{result.candidates.map((item) => <tr key={item.position_id}><td className="border p-2">{item.name}<br /><small>{statusLabel(item.maturity_status)}</small></td>
          <td className="border p-2">{item.status === 'EXCLUDED' ? 'Исключена' : item.status === 'INFORMATION_ONLY' ? 'Только сведения' : item.readiness === 'VERIFIED' ? 'Пригодность проверена' : 'Нужна проверка'}</td>
          <td className="border p-2">{item.capacity?.value?.recommended_fleet ?? '—'}</td>
          <td className="border p-2">{formatDecimal(item.technical_score) ?? '—'}{item.technical_rank && ` · место ${item.technical_rank}`}</td>
          <td className="border p-2">{item.npv_project == null ? 'не сопоставлен' : presentationValue('', item.npv_project, 'RUB')}</td>
          <td className="border p-2">{formatDecimal(item.financial_score) ?? '—'}{item.financial_rank && ` · место ${item.financial_rank}`}</td></tr>)}</tbody></table></div>
      {result.candidates.map((item) => <details key={`detail.${item.position_id}`} className="rounded border p-2 text-sm"><summary>{item.name}: причины и вклад факторов</summary>
        <p>Причины: {item.reason_codes.map(reasonLabel).join('; ') || 'препятствия не выявлены'}.</p>
        <p>Качество данных: {formatDecimal(item.data_score?.value) ?? '—'} из 100. Доли суммарного веса признаков: подтверждено {formatPercent(item.data_score?.verified_weight, 1)}, не проверено {formatPercent(item.data_score?.unverified_weight, 1)}, отсутствует {formatPercent(item.data_score?.missing_weight, 1)}. Это вес признаков по значимости, а не их количество.</p>
        <p>Пригодность: {formatDecimal(item.applicability_score) ?? '—'} из 100, вес 50 %; экономика: {formatDecimal(item.economy_score) ?? '—'} из 100, вес 35 %; качество данных: {formatDecimal(item.data_score?.value) ?? '—'} из 100, вес 15 %; поправка {formatDecimal(item.penalty) ?? '—'}. Денежный балл появляется при сопоставимых финансовых расчётах.</p>
        <ul className="list-disc pl-5">{item.components.filter((part) => componentText[part.component_id]).map((part) => <li key={part.component_id}>{componentText[part.component_id]}: {part.status === 'VALUE' ? `${formatDecimal(part.normalized_value) ?? '—'} из 100` : statusLabel(part.status)}; вес {formatPercent(part.effective_weight, 1)}. Источник: {part.provenance_refs.length ? 'характеристики сохранённого каталога' : 'не подтверждён'}</li>)}</ul>
        <p>Источники: сохранённый каталог, ограничения объекта и расчёт парка. Подробные связи доступны в техническом архиве.</p>
      </details>)}
    </>}
  </section>;
}
