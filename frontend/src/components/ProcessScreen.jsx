import { useEffect, useState } from 'react';
import AppIcon from './AppIcon';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const LABELS = { object_type: 'Объект', process_type: 'Процесс', cargo_type: 'Груз', pallets_per_day: 'Операций в сутки', avg_distance_m: 'Плечо, м', shifts_count: 'Смен', staff_headcount: 'Сотрудников' };
const VALUES = { other: 'Другой объект', transport: 'Перемещение', cleaning: 'Уборка', delivery: 'Доставка', pallets: 'Паллеты', boxes: 'Коробки', cases: 'Объекты уборки', deliveries: 'Доставки' };
const FACT_LABELS = { payload_kg: 'Грузоподъёмность', max_speed_m_s: 'Скорость', min_aisle_width_m: 'Ширина прохода', autonomy_hours: 'Автономность', navigation_type: 'Навигация' };

function sourceLabel(card) {
  const s = card.source;
  return [s.name || 'Источник не указан', s.pdf_page ? `стр. ${s.pdf_page}` : `строка ${s.source_row}`, s.observed_on ? `зафиксирован ${s.observed_on}` : null].filter(Boolean).join(' · ');
}
function factText(card) {
  return card.facts.length ? card.facts.slice(0, 5).map((f) => `${FACT_LABELS[f.code] || f.code}: ${f.value}${f.unit ? ` ${f.unit}` : ''}`).join('; ') : 'Подтверждённых характеристик нет';
}
async function post(path, body, csrf) {
  const response = await fetch(`${API}${path}`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': readCsrfCookie() } : {}) }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
  return data;
}

export default function ProcessScreen({ activeProject, user, hasResult, sessionKey, session, onSessionChange, onStartCalculation, onOpenCatalog, onOpenAccount, onConfirmDraft, onReturnToResult }) {
  const [input, setInput] = useState(session?.input || '');
  const [turns, setTurns] = useState(session?.turns || []);
  const [answer, setAnswer] = useState(session?.answer || null);
  const [webResult, setWebResult] = useState(session?.webResult || null);
  const [selected, setSelected] = useState(session?.selected || []);
  const [busy, setBusy] = useState(false);
  const [webBusy, setWebBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    onSessionChange({ key: sessionKey, value: { input, turns, answer, webResult, selected } });
  }, [sessionKey, input, turns, answer, webResult, selected, onSessionChange]);

  const send = async (event, compare = false) => {
    event?.preventDefault();
    const message = (compare ? (turns.filter((t) => t.role === 'user').at(-1)?.text || input) : input).trim();
    if (message.length < 3 || busy) return;
    setError(''); setBusy(true);
    try {
      const data = await post('/api/assistant/catalog', { message, history: turns.filter((t) => t.role === 'user').map((t) => t.text).slice(-6), project_id: activeProject?.id || null, compare_ids: compare ? selected : [] }, Boolean(activeProject));
      setAnswer(data);
      if (!compare) {
        setTurns((old) => [...old, { role: 'user', text: message }, { role: 'assistant', text: `${data.reply} ${data.question}` }].slice(-12));
        setInput(''); setSelected([]);
      }
    } catch (e) { setError(e.message || 'Каталог недоступен.'); }
    finally { setBusy(false); }
  };
  const searchWeb = async () => {
    const query = (input.trim() || turns.filter((t) => t.role === 'user').at(-1)?.text || '').slice(0, 300);
    if (!query || webBusy) return;
    if (!user) { onOpenAccount(); return; }
    setWebBusy(true); setError('');
    try { setWebResult(await post('/api/assistant/web', { query, project_id: activeProject?.id || null }, true)); }
    catch (e) { setWebResult({ status: 'unavailable', results: [], message: e.message || 'Внешний поиск недоступен.' }); }
    finally { setWebBusy(false); }
  };
  const toggle = (id) => setSelected((old) => old.includes(id) ? old.filter((item) => item !== id) : old.length < 3 ? [...old, id] : old);
  const compared = answer?.comparison || [];

  return <main className="process-screen" aria-labelledby="process-title">
    <section className="process-hero panel"><div className="process-hero-copy">
      <p className="eyebrow">РОБОДОВОД / ПРОЦЕСС</p><span className="process-status process-status-live">Поиск по активному каталогу</span>
      <h1 id="process-title">Помощник по выбору решения</h1>
      <p className="process-lead">Опишите процесс и условия. Помощник покажет позиции из активного каталога, источники и вопросы, которые нужно уточнить перед расчётом.</p>
      {activeProject && <p className="process-project">Выбран проект: <strong>{activeProject.name}</strong></p>}
      <div className="process-actions"><button type="button" className="secondary-action" onClick={onStartCalculation}>Сразу к расчёту <AppIcon name="arrow" size={16} /></button><button type="button" className="secondary-action" onClick={() => onOpenCatalog()}>Открыть библиотеку <AppIcon name="library" size={16} /></button></div>
      {hasResult && <button type="button" className="process-return" onClick={onReturnToResult}>Вернуться к результату расчёта</button>}
    </div><div className="process-hero-mark" aria-hidden="true"><AppIcon name="process" size={82} /></div></section>

    <section className="assistant-workspace" aria-label="Диалог с помощником">
      <div className="assistant-dialog panel"><header><span className="catalog-eyebrow">ДИАЛОГ</span><h2>Расскажите о задаче</h2><p>Например: «Перевозим 800 паллет в сутки по складу, плечо 180 м, 3 смены».</p></header>
        <div className="assistant-turns" aria-live="polite">{!turns.length && <p className="assistant-empty">Укажите груз или операцию, объём и ограничения. Я задам следующий вопрос и покажу совпадения в каталоге.</p>}{turns.map((t, i) => <div className={`assistant-turn ${t.role}`} key={`${i}-${t.role}`}><small>{t.role === 'user' ? 'Вы' : 'Помощник'}</small><p>{t.text}</p></div>)}</div>
        <form className="assistant-form" onSubmit={send}><label htmlFor="assistant-query">Ваш запрос</label><textarea id="assistant-query" rows="3" maxLength="400" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Какой процесс хотите роботизировать?" /><div className="assistant-form-actions"><button type="submit" className="primary-action" disabled={busy || input.trim().length < 3}>{busy ? 'Ищем…' : 'Найти в каталоге'}</button><button type="button" className="secondary-action" onClick={searchWeb} disabled={webBusy || (!input.trim() && !turns.length)}>{webBusy ? 'Ищем…' : 'Найти в интернете'}</button></div><small>Веб-поиск запускается отдельно и требует входа в аккаунт. Результаты не добавляются в каталог.</small></form>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="assistant-results">
        {answer && <section className="assistant-catalog panel" aria-label="Результаты каталога"><header><span className="catalog-eyebrow">ОФИЦИАЛЬНЫЙ КАТАЛОГ · {answer.catalog.version}</span><h2>Подходящие позиции</h2><p>{answer.reply}</p></header>
          {!answer.matches.length && <p className="assistant-empty">Точного ответа в каталоге нет. Уточните формулировку или используйте отдельный веб-поиск.</p>}
          <div className="assistant-cards">{answer.matches.map((card) => <article className="assistant-card" key={card.id}><div className="assistant-card-head"><h3>{card.name}</h3><span>{card.capacity.ready ? 'В capacity-пуле' : 'Требует данных для capacity'}</span></div><p>{card.use ? `Назначение: ${card.use}` : card.description ? `Исходное описание: ${card.description}` : 'Назначение не указано.'}</p><p className="assistant-facts">{factText(card)}</p>{card.limits && <p className="assistant-limits">Ограничения из исходного текста: {card.limits}</p>}<p className="assistant-source">Источник: {sourceLabel(card)}</p><div className="assistant-card-actions"><button type="button" onClick={() => onOpenCatalog(card.id)}>Открыть карточку</button><label><input type="checkbox" checked={selected.includes(card.id)} onChange={() => toggle(card.id)} disabled={!selected.includes(card.id) && selected.length >= 3} /> Сравнить</label></div></article>)}</div>
          {selected.length >= 2 && <button type="button" className="secondary-action assistant-compare-button" onClick={() => send(null, true)} disabled={busy}>Сравнить выбранные ({selected.length})</button>}
          <p className="assistant-caution">{answer.note}</p></section>}
        {compared.length >= 2 && <section className="assistant-comparison panel" aria-label="Сравнение позиций"><header><span className="catalog-eyebrow">СРАВНЕНИЕ</span><h2>Одинаковые критерии для {compared.length} позиций</h2></header><div className="assistant-table-wrap"><table><thead><tr><th>Критерий</th>{compared.map((c) => <th key={c.id}>{c.name}</th>)}</tr></thead><tbody>
          <tr><th>Производитель</th>{compared.map((c) => <td key={c.id}>{c.manufacturer || 'Не указан'}</td>)}</tr>
          <tr><th>Назначение</th>{compared.map((c) => <td key={c.id}>{c.use || 'Не указано'}</td>)}</tr>
          <tr><th>Ограничения</th>{compared.map((c) => <td key={c.id}>{c.limits || 'Не подтверждены в карточке'}</td>)}</tr>
          <tr><th>Подтверждённые характеристики</th>{compared.map((c) => <td key={c.id}>{factText(c)}</td>)}</tr>
          <tr><th>Capacity</th>{compared.map((c) => <td key={c.id}>{c.capacity.ready ? (c.capacity.requires_assumptions ? 'Участвует с допущениями' : 'Участвует') : 'Требует данных'}</td>)}</tr>
          <tr><th>Источник</th>{compared.map((c) => <td key={c.id}>{sourceLabel(c)}</td>)}</tr>
        </tbody></table></div></section>}
        {answer?.draft && <section className="assistant-draft panel" aria-label="Черновик для расчёта"><span className="catalog-eyebrow">ЧЕРНОВИК · НЕ ПОДТВЕРЖДЁН</span><h2>Параметры для проверки</h2><p>Эти значения извлечены из вашего описания. Проверьте их в форме перед запуском расчёта.</p><dl>{Object.entries(answer.draft.fields).map(([key, value]) => <div key={key}><dt>{LABELS[key] || key}</dt><dd>{VALUES[value] || value}</dd></div>)}</dl><button type="button" className="primary-action" onClick={() => onConfirmDraft(answer.draft)}>Подтвердить черновик и открыть расчёт</button></section>}
        {webResult && <section className="assistant-web panel" aria-label="Внешний поиск"><span className="catalog-eyebrow">ВНЕШНИЙ ПОИСК · НЕ ПРОВЕРЕНО</span><h2>Результаты интернета</h2><p>{webResult.message}</p>{webResult.searched_at && <p className="assistant-source">Время поиска: {new Date(webResult.searched_at).toLocaleString('ru-RU')}</p>}{webResult.results.map((item) => <article key={item.url}><h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3><p>{item.snippet}</p><small>{item.url}</small></article>)}</section>}
      </div>
    </section>
  </main>;
}
