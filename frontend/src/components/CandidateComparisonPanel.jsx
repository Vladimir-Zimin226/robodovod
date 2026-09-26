import { useEffect, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const reasonText = {
  OTHER_OPERATION_OR_PHYSICAL_PROFILE: 'Другая операция или физический профиль',
  RESEARCH_NOT_PURCHASE_READY: 'Исследовательская разработка',
  NO_SUPPORTED_CALCULATION_FORMULA: 'Нет поддержанной формулы',
  CAPACITY_NOT_COMPUTED: 'Парк на этих входах не рассчитан',
  PRICE_NOT_CONFIRMED: 'Цена не подтверждена',
};
const componentText = {
  availability: 'Доступность', integrations: 'Интеграции', aisle_margin: 'Запас по ширине прохода',
  trl: 'Зрелость', payload_margin: 'Запас грузоподъёмности',
};

export default function CandidateComparisonPanel({ project, capacityRunId }) {
  const [options, setOptions] = useState(null);
  const [selected, setSelected] = useState([]);
  const [constraints, setConstraints] = useState({ payload: '', aisle: '', integrations: '', confirmed: false });
  const [financeRuns, setFinanceRuns] = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
        setOptions(body);
        setSelected([body.source_position_id].filter(Boolean));
      })
      .catch((reason) => { if (reason.name !== 'AbortError') setError(`Не удалось загрузить варианты сравнения: ${reason.message}. Повторите после обновления страницы.`); });
    return () => controller.abort();
  }, [project?.id, capacityRunId]);

  const compare = async () => {
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
      setResult(body);
    } catch (reason) { setError(`Сравнение недоступно: ${reason.message || 'ошибка сервера'}. Выбор моделей сохранён на этой странице; повторите запрос.`); }
    finally { setBusy(false); }
  };

  const change = (positionId) => {
    setSelected((current) => current.includes(positionId) ? current.filter((id) => id !== positionId)
      : current.length < 3 ? [...current, positionId] : current);
    setResult(null);
  };
  const constraint = (key, value) => { setConstraints((current) => ({ ...current, [key]: value, confirmed: key === 'confirmed' ? value : false })); setResult(null); };
  if (!project?.id || !capacityRunId) return <section className="panel p-4 text-sm" aria-label="Сравнение кандидатов для операции">
    <h2 className="text-lg font-semibold">Сравнить модели для этой операции</h2>
    <p>Сначала сохраните расчёт парка в проекте. Затем выберите 2–3 совместимые модели и нажмите «Сравнить».</p>
  </section>;
  const selectedNames = selected.map((id) => options?.items.find((item) => item.position_id === id)?.name).filter(Boolean);
  const eligibleSelected = selected.filter((id) => { const item = options?.items.find((row) => row.position_id === id);
    return item?.calculation_ready && item?.maturity_status !== 'RND'; });
  const missingFinance = eligibleSelected.filter((id) => !financeRuns[id]);
  return <section className="panel space-y-3 p-4" aria-label="Сравнение кандидатов для операции">
    <h2 className="text-lg font-semibold">Сравнить модели для этой операции</h2>
    <p className="text-sm">Сохранённый расчёт парка задаёт общие входы. Выберите ещё 1–2 модели с тем же физическим профилем и нажмите «Сравнить». Технический и денежный выводы проверяются отдельно; сохранённые расчёты не меняются.</p>
    {!options && !error && <p role="status" className="text-sm">Загружаем совместимые модели для сохранённого расчёта…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {options && <>
      <p className="text-sm">Сравниваются: {selectedNames.length ? selectedNames.join(' и ') : 'модели ещё не выбраны'}.</p>
      {options.items.length < 2 && <p role="status" className="text-sm text-amber-800">В активном каталоге нет второй модели с тем же расчётным профилем. Техническое сравнение пока недоступно.</p>}
      <p className="text-xs">В активном каталоге {options.items.length} позиции с тем же физическим профилем.</p>
      <div className="grid gap-2 sm:grid-cols-2">{options.items.map((item) => <label key={item.position_id} className="rounded border p-2 text-sm">
        <input type="checkbox" checked={selected.includes(item.position_id)} disabled={!selected.includes(item.position_id) && selected.length >= 3} onChange={() => change(item.position_id)} />{' '}
        {item.name} <span className="text-slate-500">· {item.maturity_status === 'RND' ? 'исследовательская' : item.calculation_ready ? 'есть расчётный профиль' : 'только сведения'} · цена {item.price_status}</span>
      </label>)}</div>
      <details><summary>Ограничения объекта и финансовые runs</summary>
        <p className="text-sm">Ограничения применяются ко всем позициям одинаково. Неизвестный паспорт остаётся неподтверждённым.</p>
        <div className="flex flex-wrap gap-2 text-sm">
          <label>Масса паллеты, кг <input aria-label="Масса паллеты" className="w-24 rounded border p-1" value={constraints.payload} onChange={(e) => constraint('payload', e.target.value)} /></label>
          <label>Доступная ширина прохода, м <input aria-label="Ширина прохода" className="w-24 rounded border p-1" value={constraints.aisle} onChange={(e) => constraint('aisle', e.target.value)} /></label>
          <label>Нужные интеграции, через запятую <input aria-label="Нужные интеграции" className="w-44 rounded border p-1" value={constraints.integrations} onChange={(e) => constraint('integrations', e.target.value)} /></label>
          <label><input type="checkbox" checked={constraints.confirmed} onChange={(e) => constraint('confirmed', e.target.checked)} /> Подтверждаю ограничения</label>
        </div>
        <p className="mt-2 text-sm">Для денежного сравнения выберите сохранённый полный финансовый run каждой допустимой позиции. Сервер повторно проверит исходный C11, одинаковые входы и условия. Пустой выбор оставляет денежный вывод недоступным.</p>
        {selected.map((id) => <label key={id} className="mt-1 block text-sm">{options.items.find((item) => item.position_id === id)?.name} — финансовый run{' '}
          <select aria-label={`Финансовый run ${id}`} className="max-w-full rounded border p-1" value={financeRuns[id] || ''} onChange={(e) => { setFinanceRuns((current) => ({ ...current, [id]: e.target.value })); setResult(null); }}>
            <option value="">Не выбран</option>{(options.finance_options || []).filter((item) => item.position_id === id).map((item) => <option key={item.run_id} value={item.run_id}>{item.created_at ? new Date(item.created_at).toLocaleString('ru-RU') : item.run_id} · NPV {item.npv_project} ₽ · условия {item.basis_digest.slice(0, 18)}</option>)}
          </select></label>)}
      </details>
      <p role="status" className="text-sm">{selected.length < 2 ? 'Выберите вторую модель.' : selected.length > eligibleSelected.length ? 'Непроверенная или исследовательская модель останется информационной; технический балл возможен только для расчётных моделей.' : 'Можно сравнить технические показатели.'} {missingFinance.length ? `Денежное сравнение недоступно: для ${missingFinance.map((id) => options.items.find((item) => item.position_id === id)?.name).join(', ')} нет выбранного сопоставимого полного финансового расчёта.` : 'Для денежного вывода сервер ещё проверит общие условия финансовых расчётов.'}</p>
      <button type="button" className="primary-action" disabled={busy || selected.length < 2} onClick={compare}>{busy ? 'Сравниваем…' : 'Сравнить выбранные позиции'}</button>
    </>}
    {result && <>
      <p className="text-sm">Все модели пересчитаны на входах выбранного сохранённого расчёта.</p>
      {result.role_scope.affected_role_code === 'forklift_driver' && <p className="text-sm text-amber-800">Для паллетной перевозки учитывается только труд водителя погрузчика в подтверждённом C14. Экономия комплектовщиков, сортировщиков и упаковщиков сюда не входит.</p>}
      <p className="text-sm"><strong>Технический вывод:</strong> {result.technical_recommendation.reason}. <strong>Денежный вывод:</strong> {result.financial_recommendation.reason}.</p>
      <div className="overflow-x-auto"><table className="w-full min-w-[780px] border-collapse text-sm"><thead><tr><th className="border p-2">Модель</th><th className="border p-2">Допуск</th><th className="border p-2">Парк</th><th className="border p-2">Технический балл</th><th className="border p-2">NPV</th><th className="border p-2">Денежный балл</th></tr></thead>
        <tbody>{result.candidates.map((item) => <tr key={item.position_id}><td className="border p-2">{item.name}<br /><small>{item.maturity_status}</small></td>
          <td className="border p-2">{item.status === 'EXCLUDED' ? 'Исключена' : item.status === 'INFORMATION_ONLY' ? 'Только сведения' : item.readiness === 'VERIFIED' ? 'Пригодность проверена' : 'Нужна проверка'}</td>
          <td className="border p-2">{item.capacity?.value?.recommended_fleet ?? '—'}</td>
          <td className="border p-2">{item.technical_score ?? '—'}{item.technical_rank && ` · место ${item.technical_rank}`}</td>
          <td className="border p-2">{item.npv_project == null ? 'не сопоставлен' : `${item.npv_project} ₽`}</td>
          <td className="border p-2">{item.financial_score ?? '—'}{item.financial_rank && ` · место ${item.financial_rank}`}</td></tr>)}</tbody></table></div>
      {result.candidates.map((item) => <details key={`detail.${item.position_id}`} className="rounded border p-2 text-sm"><summary>{item.name}: причины и вклад факторов</summary>
        <p>Причины: {item.reason_codes.map((code) => reasonText[code] || code).join('; ') || 'нет'}.</p>
        <p>Качество данных: {item.data_score?.value ?? '—'}; проверено {item.data_score?.verified_weight ?? 0}, без проверки {item.data_score?.unverified_weight ?? 0}, отсутствует {item.data_score?.missing_weight ?? 0}.</p>
        <p>Факторы C19: пригодность {item.applicability_score ?? '—'} × 0,50; экономика {item.economy_score ?? '—'} × 0,35; качество данных {item.data_score?.value ?? '—'} × 0,15; поправка {item.penalty}. Денежный балл появляется только при сопоставимых финансовых runs.</p>
        <ul className="list-disc pl-5">{item.components.map((part) => <li key={part.component_id}>{componentText[part.component_id] || part.component_id}: {part.status === 'VALUE' ? part.normalized_value : part.status}; вес {part.effective_weight}; источник {part.provenance_refs.join(', ') || 'неизвестен'}</li>)}</ul>
        <p>Источники снимков: {item.source_refs.join(', ') || 'расчётный снимок отсутствует'}.</p>
      </details>)}
    </>}
  </section>;
}
