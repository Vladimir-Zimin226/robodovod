import { useEffect, useMemo, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import CatalogPositionDialog from './CatalogPositionDialog';
import CandidateComparisonPanel from './CandidateComparisonPanel';

const API = import.meta.env.VITE_API_URL || '';
const TOPICS = { passport: 'Паспорт', price: 'Цена', service: 'Сервис', availability: 'Доступность' };

async function responseJson(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
  return body;
}

function factText(cell) {
  return cell.value == null ? 'Нет данных' : `${cell.value}${cell.unit ? ` ${cell.unit}` : ''}`;
}

export default function RoboExpertScreen({ user, project, capacityRunId, onOpenAccount }) {
  const [catalog, setCatalog] = useState(null);
  const [selected, setSelected] = useState([]);
  const [query, setQuery] = useState('');
  const [comparison, setComparison] = useState(null);
  const [summary, setSummary] = useState(null);
  const [web, setWeb] = useState(null);
  const [detail, setDetail] = useState(null);
  const [topic, setTopic] = useState('passport');
  const [webPosition, setWebPosition] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/api/roboexpert/options`, { signal: controller.signal }).then(responseJson)
      .then((value) => { setCatalog(value); setError(''); })
      .catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, []);

  const items = useMemo(() => catalog?.items || [], [catalog]);
  const chosen = items.filter((item) => selected.includes(item.position_id));
  const classKey = chosen[0]?.class_key;
  const search = query.trim().toLocaleLowerCase('ru-RU');
  const visible = useMemo(() => items.filter((item) => !search || [item.name, item.manufacturer, item.type_code]
    .some((value) => String(value || '').toLocaleLowerCase('ru-RU').includes(search))), [items, search]);
  const comparable = visible.filter((item) => item.calculation_ready && item.maturity_status !== 'RND');
  const informational = visible.filter((item) => !item.calculation_ready || item.maturity_status === 'RND');

  const toggle = (item) => {
    setSelected((current) => current.includes(item.position_id) ? current.filter((id) => id !== item.position_id)
      : current.length >= 3 || (classKey && classKey !== item.class_key) ? current : [...current, item.position_id]);
    setComparison(null); setSummary(null); setWeb(null); setError('');
  };
  const compare = async () => {
    setBusy('compare'); setError(''); setSummary(null); setWeb(null);
    try {
      setComparison(await responseJson(await fetch(`${API}/api/roboexpert/compare`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_ids: selected, catalog_version: catalog.catalog_version }),
      })));
      setWebPosition(selected[0]);
    } catch (reason) { setComparison(null); setError(reason.message); }
    finally { setBusy(''); }
  };
  const aiSummary = async () => {
    if (!user) { onOpenAccount(); return; }
    setBusy('summary'); setError('');
    try {
      setSummary(await responseJson(await fetch(`${API}/api/roboexpert/summary`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ position_ids: selected, catalog_version: catalog.catalog_version,
          comparison_digest: comparison.comparison_digest }),
      })));
    } catch (reason) { setError(reason.message); }
    finally { setBusy(''); }
  };
  const webSearch = async () => {
    if (!user) { onOpenAccount(); return; }
    setBusy('web'); setError('');
    try {
      setWeb(await responseJson(await fetch(`${API}/api/roboexpert/web`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ position_id: webPosition, catalog_version: catalog.catalog_version, topic }),
      })));
    } catch (reason) { setError(reason.message); }
    finally { setBusy(''); }
  };
  const openDetail = (id) => {
    const item = items.find((value) => value.position_id === id);
    setDetail({ id, position_id: id, name: item?.name, manufacturer: item?.manufacturer,
      type_code: item?.type_code });
  };

  return <main className="roboexpert-screen" aria-label="Робоэксперт">
    <header className="roboexpert-card">
      <p className="roboexpert-eyebrow">Активный каталог · {catalog?.catalog_version || 'загрузка'}</p>
      <h1>Робоэксперт</h1>
      <p>Сравните 2–3 расчётные позиции одного класса. Сведения каталога, рейтинг сохранённого расчёта, ответ AI и веб-поиск показываются отдельно.</p>
      <p>Сравнение каталога не меняет ваш проект, расчёты или официальный каталог.</p>
    </header>
    {error && <p className="roboexpert-error" role="alert">{error}</p>}
    <section className="roboexpert-card" aria-label="Выбор роботов">
      <h2>Выберите позиции</h2>
      <label className="roboexpert-search">Поиск по названию, производителю или классу
        <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Например, паллетный транспорт" /></label>
      {classKey && <p>Выбранный расчётный класс: <strong>{chosen[0]?.calculation_profile}</strong>. Позиции другого класса доступны после снятия выбора.</p>}
      <div className="roboexpert-list">{comparable.map((item) => <article key={item.position_id} className="roboexpert-option">
        <input id={`roboexpert.${item.position_id}`} type="checkbox" checked={selected.includes(item.position_id)} disabled={!selected.includes(item.position_id) && (selected.length >= 3 || (classKey && classKey !== item.class_key))} onChange={() => toggle(item)} />
        <label htmlFor={`roboexpert.${item.position_id}`}><strong>{item.name}</strong><small>{item.manufacturer || 'Производитель не указан'} · {item.type_code} · расчётный профиль {item.calculation_profile}</small></label>
        <button type="button" onClick={() => openDetail(item.position_id)}>Карточка</button>
      </article>)}</div>
      {catalog && comparable.length === 0 && <p>Расчётные позиции по этому запросу не найдены.</p>}
      <button type="button" className="primary-action" disabled={selected.length < 2 || busy !== ''} onClick={compare}>{busy === 'compare' ? 'Сравниваем…' : 'Сравнить выбранные'}</button>
    </section>

    {comparison && <section className="roboexpert-card" aria-label="Структурированное сравнение">
      <h2>Сравнение по каталогу</h2>
      <p>Версия {comparison.catalog_version}; числовые поля сопоставимы только при одинаковых единицах и подтверждённых источниках.</p>
      <div className="roboexpert-table-scroll"><table><thead><tr><th>Параметр</th>{comparison.positions.map((item) => <th key={item.position_id}>{item.name}</th>)}</tr></thead><tbody>
        {comparison.criteria.map((row) => <tr key={row.code}><th>{row.label}<small>{row.numeric_comparable ? 'Сопоставимо' : 'Без числового вывода'}</small></th>
          {row.cells.map((cell, index) => <td key={`${row.code}.${comparison.positions[index].position_id}`}><strong>{factText(cell)}</strong><small>{cell.confirmed ? 'Подтверждено' : cell.status === 'MISSING' ? 'Нет данных' : 'Требует проверки'}</small><small>Источник: {cell.source.evidence_id || 'не указан'} · <a href={cell.source.card_url} target="_blank" rel="noreferrer">карточка каталога</a></small></td>)}</tr>)}
        <tr><th>Цена покупки<small>{comparison.price.comparable ? 'Сопоставимо' : 'Вывод о дешевизне недоступен'}</small></th>{comparison.price.cells.map((cell, index) => <td key={`price.${comparison.positions[index].position_id}`}><strong>{factText(cell)}</strong><small>{cell.confirmed ? 'Подтверждено' : cell.value == null ? 'Нет цены' : 'Цена требует проверки'}</small><small>Источник: {cell.source.evidence_id || 'не указан'} · <a href={cell.source.card_url} target="_blank" rel="noreferrer">карточка каталога</a></small></td>)}</tr>
      </tbody></table></div>
      <h3>Что известно и что проверить</h3>
      {comparison.summary.advantages.map((item) => <p key={item}>{item}</p>)}
      <ul>{comparison.summary.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      <ul>{comparison.summary.verify_on_site.map((item) => <li key={item}>{item}</li>)}</ul>
      <p className="roboexpert-disclaimer">Техническая пригодность и закупочная готовность здесь не установлены. Рейтинг по операции находится ниже и требует сохранённого C11.</p>
      <div className="roboexpert-research">
        <section><h3>Пояснение AI Studio</h3><p>DeepSeek V4 Flash пересказывает структурированные факты. Его ответ не меняет баллы и статусы каталога.</p>
          <button type="button" className="secondary-action" disabled={busy !== ''} onClick={aiSummary}>{busy === 'summary' ? 'Формируем…' : user ? 'Составить пояснение' : 'Войти для AI-пояснения'}</button>
          {summary && <div className="roboexpert-external"><strong>Ответ модели · {summary.model || 'AI Studio'}</strong><p>{summary.status === 'OK' ? summary.text : summary.message}</p>{summary.usage && <small>Токены: {summary.usage.input_tokens} вход / {summary.usage.output_tokens} выход · оценка {summary.usage.estimated_rub} ₽. {summary.usage.cost_note} <a href={summary.usage.pricing_url} target="_blank" rel="noreferrer">Тариф</a></small>}<small>Вызовы сегодня: {summary.limits.user_calls_today}/{summary.limits.user_daily_limit}</small></div>}</section>
        <section><h3>Адресная проверка в интернете</h3><p>Результаты Yandex Search API требуют проверки и не входят в официальный каталог или расчёт.</p>
          <label>Позиция<select value={webPosition} onChange={(event) => { setWebPosition(event.target.value); setWeb(null); }}>{comparison.positions.map((item) => <option key={item.position_id} value={item.position_id}>{item.name}</option>)}</select></label>
          <label>Что искать<select value={topic} onChange={(event) => { setTopic(event.target.value); setWeb(null); }}>{Object.entries(TOPICS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
          <button type="button" className="secondary-action" disabled={busy !== ''} onClick={webSearch}>{busy === 'web' ? 'Ищем…' : user ? 'Проверить свежие сведения' : 'Войти для веб-поиска'}</button>
          {web && <div className="roboexpert-external"><strong>Веб-поиск · требует проверки · {new Date(web.searched_at).toLocaleString('ru-RU')}</strong><p>{web.message}</p><ul>{web.results.map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a><p>{item.snippet}</p></li>)}</ul><small>{web.cost_note} Дневной синхронный запрос: {web.pricing_estimate.daytime_synchronous_request_rub} ₽ по тарифу от {web.pricing_estimate.checked_on}. <a href={web.pricing_estimate.source_url} target="_blank" rel="noreferrer">Тариф</a></small><small>Вызовы сегодня: {web.limits.user_calls_today}/{web.limits.user_daily_limit}</small></div>}</section>
      </div>
    </section>}

    <section className="roboexpert-card" aria-label="Информационные позиции"><h2>Информационные решения каталога</h2>
      <p>G2P, Pick by Voice/Light и исследовательские комплектовщики могут быть в каталоге, но не получают балл или расчёт парка без поддержанной формулы и проверенных входов.</p>
      <div className="roboexpert-list">{informational.map((item) => <article className="roboexpert-option" key={item.position_id}><span><strong>{item.name}</strong><small>{item.type_code} · {item.information_reason || 'Исследовательская позиция'}</small></span><button type="button" onClick={() => openDetail(item.position_id)}>Карточка</button></article>)}</div>
      {catalog && informational.length === 0 && <p>По этому запросу информационных позиций нет.</p>}
    </section>

    <section className="roboexpert-card" aria-label="Рейтинг для выбранной операции"><h2>Рейтинг для вашей операции</h2>
      {project?.id && capacityRunId ? <CandidateComparisonPanel key={`${project.id}:${capacityRunId}`} project={project} capacityRunId={capacityRunId} />
        : <p>Откройте сохранённый расчёт парка C11 в проекте. Тогда появятся баллы C19, вклад факторов, причины исключения и статус расчётной доступности на одних входах операции.</p>}
    </section>
    {detail && <CatalogPositionDialog position={detail} official onClose={() => setDetail(null)} />}
  </main>;
}
