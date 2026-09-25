import { useEffect, useState } from 'react';
import AppIcon from './AppIcon';
import { readCsrfCookie } from '../persistenceApi';
import { STARTER_QUESTIONS, INTERVIEW_FIELDS, INTERVIEW_STEPS, emptyProfile,
  editProfile, confirmField, mergeAssistantDraft, profileReadiness, canImportProfile,
  readGuestProfile, writeGuestProfile } from '../assistantInterview';

const API = import.meta.env.VITE_API_URL || '';
const FACT_LABELS = { payload_kg: 'Грузоподъёмность', max_speed_m_s: 'Скорость', min_aisle_width_m: 'Ширина прохода', autonomy_hours: 'Автономность', navigation_type: 'Навигация' };
const guestStorage = () => { try { return window.sessionStorage; } catch { return null; } };

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
  const [profile, setProfile] = useState(() => !activeProject ? readGuestProfile(guestStorage()) : emptyProfile());
  const [profileLoading, setProfileLoading] = useState(Boolean(activeProject));
  const [profileStatus, setProfileStatus] = useState('');
  const [conflicts, setConflicts] = useState([]);
  const [step, setStep] = useState(0);
  const projectId = activeProject?.id;
  const editField = (key, value) => {
    setProfile((current) => editProfile(current, key, value));
    if (projectId) setProfileStatus('Есть несохранённые изменения.');
  };
  const setConfirmed = (key, value) => {
    setProfile((current) => confirmField(current, key, value));
    if (projectId) setProfileStatus('Есть несохранённые изменения.');
  };

  useEffect(() => {
    if (!projectId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/assistant/projects/${projectId}/profile`, { credentials: 'include', signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Не удалось загрузить черновик проекта.')))
      .then((data) => { if (!controller.signal.aborted) setProfile(data.profile || emptyProfile()); })
      .catch((loadError) => { if (!controller.signal.aborted) setProfileStatus(loadError.message); })
      .finally(() => { if (!controller.signal.aborted) setProfileLoading(false); });
    return () => controller.abort();
  }, [projectId]);

  useEffect(() => { if (!activeProject) writeGuestProfile(guestStorage(), profile); }, [activeProject, profile]);

  const saveProfile = async () => {
    if (!activeProject) return;
    setProfileStatus('Сохраняем…');
    try {
      await fetch(`${API}/api/assistant/projects/${activeProject.id}/profile`, {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(profile),
      }).then((response) => response.ok ? response.json() : Promise.reject(new Error('Не удалось сохранить черновик.')));
      setProfileStatus('Черновик сохранён в проекте.');
      return true;
    } catch (saveError) { setProfileStatus(saveError.message); return false; }
  };

  useEffect(() => {
    onSessionChange({ key: sessionKey, value: { input, turns, answer, webResult, selected, profile } });
  }, [sessionKey, input, turns, answer, webResult, selected, profile, onSessionChange]);

  const send = async (event, compare = false, suggestedQuestion = '') => {
    event?.preventDefault();
    const message = (suggestedQuestion || (compare ? (turns.filter((t) => t.role === 'user').at(-1)?.text || input) : input)).trim();
    if (message.length < 3 || busy) return;
    setError(''); setBusy(true);
    try {
      const data = await post('/api/assistant/catalog', { message, history: turns.filter((t) => t.role === 'user').map((t) => t.text).slice(-6), project_id: activeProject?.id || null, compare_ids: compare ? selected : [] }, Boolean(activeProject));
      setAnswer(data);
      if (!compare) {
        if (data.draft) {
          setProfile((current) => {
            const merged = mergeAssistantDraft(current, data.draft);
            setConflicts(merged.conflicts);
            return merged.profile;
          });
          setProfileStatus(activeProject ? 'Новые предложения ещё не сохранены в проекте.' : 'Черновик хранится в этой вкладке 8 часов.');
        }
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
  const readiness = profileReadiness(profile);
  const fieldLabel = (key) => INTERVIEW_FIELDS.find((field) => field.key === key)?.label || key;

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
        <div className="mb-4 flex flex-wrap gap-2" aria-label="Начальные вопросы">{STARTER_QUESTIONS.map((question) => <button key={question} type="button" className="secondary-action text-xs" onClick={() => send(null, false, question)} disabled={busy}>{question}</button>)}</div>
        <div className="assistant-turns" aria-live="polite">{!turns.length && <p className="assistant-empty">Укажите груз или операцию, объём и ограничения. Я задам следующий вопрос и покажу совпадения в каталоге.</p>}{turns.map((t, i) => <div className={`assistant-turn ${t.role}`} key={`${i}-${t.role}`}><small>{t.role === 'user' ? 'Вы' : 'Помощник'}</small><p>{t.text}</p></div>)}</div>
        <form className="assistant-form" onSubmit={send}><label htmlFor="assistant-query">Ваш запрос</label><textarea id="assistant-query" rows="3" maxLength="400" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Какой процесс хотите роботизировать?" /><div className="assistant-form-actions"><button type="submit" className="primary-action" disabled={busy || input.trim().length < 3}>{busy ? 'Ищем…' : 'Найти в каталоге'}</button><button type="button" className="secondary-action" onClick={searchWeb} disabled={webBusy || (!input.trim() && !turns.length)}>{webBusy ? 'Ищем…' : 'Найти в интернете'}</button></div><small>Веб-поиск запускается отдельно и требует входа в аккаунт. Результаты не добавляются в каталог.</small></form>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="assistant-results">
        <section className="assistant-draft panel" aria-label="Интервью и черновик">
          <span className="catalog-eyebrow">ИНТЕРВЬЮ · РАСЧЁТ НЕ ЗАПУСКАЕТСЯ</span><h2>Профиль процесса</h2>
          <p>Ответьте по шагам. Предложения из диалога остаются неподтверждёнными, пока вы не проверите каждое поле.</p>
          <p>{activeProject ? `Черновик проекта «${activeProject.name}»` : 'Гостевой черновик хранится в этой вкладке 8 часов.'}</p>
          {profileLoading ? <p role="status">Загружаем черновик…</p> : <>
            <nav className="mt-3 flex flex-wrap gap-2" aria-label="Шаги интервью">{INTERVIEW_STEPS.map((name, index) => <button key={name} type="button" className="secondary-action text-xs" aria-current={step === index ? 'step' : undefined} onClick={() => setStep(index)}>{index + 1}. {name}</button>)}</nav>
            <div className="mt-3 grid gap-3">{INTERVIEW_FIELDS.filter((field) => field.step === INTERVIEW_STEPS[step] && (field.key !== 'units_per_trip' || profile.fields.process_type?.value === 'transport')).map((field) => {
              const entry = profile.fields[field.key];
              return <div key={field.key} className="rounded border p-3"><label className="block text-sm font-semibold">{field.label}
                {field.kind === 'choice' ? <select className="mt-1 w-full rounded border p-2" value={entry?.value || ''} onChange={(event) => editField(field.key, event.target.value)}>
                  <option value="">Неизвестно</option>{field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select> : <input className="mt-1 w-full rounded border p-2" type={field.kind === 'number' ? 'number' : 'text'} min={field.kind === 'number' ? '0' : undefined} value={entry?.value || ''} onChange={(event) => editField(field.key, event.target.value)} />}
              </label>{entry && <><p className="mt-1 text-xs">Источник: {entry.source === 'USER_STATEMENT' ? 'ваше описание в диалоге' : 'ввод в интервью'}{entry.evidence ? ` · «${entry.evidence}»` : ''}</p>
                <label className="mt-1 flex gap-2 text-xs"><input type="checkbox" checked={entry.confirmed} onChange={(event) => setConfirmed(field.key, event.target.checked)} />Подтверждаю значение и источник</label></>}
              </div>;
            })}</div>
            <div className="mt-3 flex gap-2"><button type="button" className="secondary-action" disabled={step === 0} onClick={() => setStep((value) => value - 1)}>Назад</button><button type="button" className="secondary-action" disabled={step === INTERVIEW_STEPS.length - 1} onClick={() => setStep((value) => value + 1)}>Далее</button></div>
            <p className="mt-3 text-sm">Для C11 ещё нужно: {readiness.capacity.length ? readiness.capacity.map(fieldLabel).join(', ') : 'обязательные поля подтверждены; затем выберите модель и подтвердите её допущения'}.</p>
            <p className="text-sm">Для труда ещё нужно: {readiness.labour.length ? readiness.labour.map(fieldLabel).join(', ') : 'поля персонала подтверждены; ручную выработку уточните после C11'}.</p>
            <p className="text-sm">Для полной экономики: {readiness.economics[0]}.</p><p className="text-sm">Для 2D: {readiness.visualization[0]}.</p>
            {readiness.unconfirmed.length > 0 && <p className="text-sm text-amber-700">Не подтверждено: {readiness.unconfirmed.map(fieldLabel).join(', ')}.</p>}
            {readiness.invalid.length > 0 && <p role="alert" className="text-sm text-red-700">Проверьте значения: {readiness.invalid.map(fieldLabel).join(', ')}. Объём и график должны быть положительными, смены × часы ≤ 24, зарплата может быть нулевой.</p>}
            {conflicts.length > 0 && <p role="alert" className="text-sm text-amber-700">Новое описание противоречит сохранённым полям: {conflicts.map(fieldLabel).join(', ')}. Проверьте их вручную; помощник не заменил значения.</p>}
            <p className="text-xs">Пиковый множитель остаётся заметкой: v2 C03 пока не имеет отдельного поля для пика. Зарплата переносится как monthly gross только после вашего подтверждения.</p>
            {profile.fields.process_type?.value === 'transport' && <p className="text-xs">Объём в сутки и плечо не определяют, сколько единиц робот везёт за рейс. Для своего процесса укажите это число сами; один расчёт охватывает один процесс в одной зоне.</p>}
            {activeProject && <button type="button" className="secondary-action mt-2" onClick={saveProfile}>Сохранить черновик в проекте</button>}
            {profileStatus && <p role="status" className="text-xs">{profileStatus}</p>}
            <button type="button" className="primary-action mt-2" disabled={!canImportProfile(profile)} onClick={async () => {
              if (!activeProject && Object.keys(readGuestProfile(guestStorage()).fields).length === 0) {
                setProfile(emptyProfile()); setProfileStatus('Срок гостевого черновика истёк. Заполните интервью заново.'); return;
              }
              if (!activeProject || await saveProfile()) onConfirmDraft(profile);
            }}>Перенести подтверждённые поля в расчёт v2</button>
          </>}
        </section>
        {answer && <section className="assistant-catalog panel" aria-label="Результаты каталога"><header><span className="catalog-eyebrow">ОФИЦИАЛЬНЫЙ КАТАЛОГ · {answer.catalog.version}</span><h2>{answer.mode === 'guidance' ? 'Ответ по сервису' : 'Совпадения в каталоге'}</h2><p>{answer.reply}</p></header>
          {!answer.matches.length && answer.mode !== 'guidance' && <p className="assistant-empty">Точного ответа в каталоге нет. Уточните формулировку или используйте отдельный веб-поиск.</p>}
          <div className="assistant-cards">{answer.matches.map((card) => <article className="assistant-card" key={card.id}><div className="assistant-card-head"><h3>{card.name}</h3><span>{card.capacity.ready ? 'В capacity-пуле' : 'Требует данных для capacity'}</span></div><p>{card.use ? `Назначение: ${card.use}` : card.description ? `Исходное описание: ${card.description}` : 'Назначение не указано.'}</p><p className="assistant-facts">{factText(card)}</p>{card.limits && <p className="assistant-limits">Ограничения из исходного текста: {card.limits}</p>}<p className="assistant-source">Источник: <a href={card.source.card_url} target="_blank" rel="noreferrer">{sourceLabel(card)}</a></p><div className="assistant-card-actions"><button type="button" onClick={() => onOpenCatalog(card.id)}>Открыть карточку</button><label><input type="checkbox" checked={selected.includes(card.id)} onChange={() => toggle(card.id)} disabled={!selected.includes(card.id) && selected.length >= 3} /> Сравнить</label></div></article>)}</div>
          {selected.length >= 2 && <button type="button" className="secondary-action assistant-compare-button" onClick={() => send(null, true)} disabled={busy}>Сравнить выбранные ({selected.length})</button>}
          <p className="assistant-caution">{answer.note}</p></section>}
        {compared.length >= 2 && <section className="assistant-comparison panel" aria-label="Сравнение позиций"><header><span className="catalog-eyebrow">СРАВНЕНИЕ</span><h2>Одинаковые критерии для {compared.length} позиций</h2></header><div className="assistant-table-wrap"><table><thead><tr><th>Критерий</th>{compared.map((c) => <th key={c.id}>{c.name}</th>)}</tr></thead><tbody>
          <tr><th>Производитель</th>{compared.map((c) => <td key={c.id}>{c.manufacturer || 'Не указан'}</td>)}</tr>
          <tr><th>Назначение</th>{compared.map((c) => <td key={c.id}>{c.use || 'Не указано'}</td>)}</tr>
          <tr><th>Ограничения</th>{compared.map((c) => <td key={c.id}>{c.limits || 'Не подтверждены в карточке'}</td>)}</tr>
          <tr><th>Подтверждённые характеристики</th>{compared.map((c) => <td key={c.id}>{factText(c)}</td>)}</tr>
          <tr><th>Capacity</th>{compared.map((c) => <td key={c.id}>{c.capacity.ready ? (c.capacity.requires_assumptions ? 'Участвует с допущениями' : 'Участвует') : 'Требует данных'}</td>)}</tr>
          {(answer.comparison_criteria || []).map((criterion) => <tr key={criterion.code}><th>{criterion.label}</th>{criterion.values.map((value, index) => <td key={compared[index].id}>{value.status === 'KNOWN' ? <>{value.value} {value.unit || ''}<br /><a href={value.card_url} target="_blank" rel="noreferrer">Источник · {value.evidence_id}</a></> : 'Нет подтверждённого значения'}</td>)}</tr>)}
          <tr><th>Источник</th>{compared.map((c) => <td key={c.id}><a href={c.source.card_url} target="_blank" rel="noreferrer">{sourceLabel(c)}</a></td>)}</tr>
        </tbody></table></div></section>}
        {webResult && <section className="assistant-web panel" aria-label="Внешний поиск"><span className="catalog-eyebrow">ВНЕШНИЙ ПОИСК · НЕ ПРОВЕРЕНО</span><h2>Результаты интернета</h2><p>{webResult.message}</p>{webResult.searched_at && <p className="assistant-source">Время поиска: {new Date(webResult.searched_at).toLocaleString('ru-RU')}</p>}{webResult.results.map((item) => <article key={item.url}><h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3><p>{item.snippet}</p><small>{item.url}</small></article>)}</section>}
      </div>
    </section>
  </main>;
}
