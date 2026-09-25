import { useEffect, useRef, useState } from 'react';
import knowledge from '../../../contracts/service-assistant-knowledge-v1.json' with { type: 'json' };
import AppIcon from './AppIcon';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';

export default function ProcessScreen({ activeProject, user, hasResult, sessionKey, session, onSessionChange,
  onStartCalculation, onOpenCatalog, onOpenDemo, onOpenProjects, onReturnToResult }) {
  const previous = session?.mode === 'service' ? session : null;
  const [input, setInput] = useState(previous?.input || '');
  const [turns, setTurns] = useState(previous?.turns || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    onSessionChange({ key: sessionKey, value: { mode: 'service', input, turns } });
  }, [sessionKey, input, turns, onSessionChange]);

  const send = async (event, suggestedQuestion = '') => {
    event?.preventDefault();
    const message = (suggestedQuestion || input).trim();
    if (message.length < 3 || busy) return;
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`${API}/api/assistant/service`, {
        method: 'POST', credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(activeProject ? { 'X-CSRF-Token': readCsrfCookie() } : {}),
        },
        body: JSON.stringify({ message, project_id: activeProject?.id || null }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Справка временно недоступна. Повторите попытку.');
      if (data.schema_version !== knowledge.version || !Array.isArray(data.actions) || typeof data.reply !== 'string') {
        throw new Error('Ответ справки имеет неизвестную версию. Обновите страницу.');
      }
      setTurns((current) => [...current, { role: 'user', text: message },
        { role: 'assistant', text: data.reply, actions: data.actions }].slice(-20));
      setInput('');
      inputRef.current?.focus();
    } catch (reason) {
      setError(reason.message || 'Справка временно недоступна. Повторите попытку.');
    } finally {
      setBusy(false);
    }
  };

  const follow = (id) => {
    if (id === 'demo') onOpenDemo();
    else if (id === 'calculation') onStartCalculation();
    else if (id === 'catalog') onOpenCatalog();
    else if (id === 'projects') onOpenProjects();
    else if (id === 'result') hasResult ? onReturnToResult() : onOpenProjects();
  };

  return <main className="process-screen service-assistant-screen" aria-labelledby="process-title">
    <section className="process-hero panel"><div className="process-hero-copy">
      <p className="eyebrow">РОБОДОВОД / СПРАВКА</p>
      <span className="process-status process-status-live">Как пользоваться сервисом</span>
      <h1 id="process-title">Помощник по сервису</h1>
      <p className="process-lead">Спросите о расчёте, каталоге, допущениях или отчётах. Помощник объяснит, что умеет РОБОДОВОД и куда перейти дальше.</p>
      {activeProject && <p className="process-project">Выбран проект: <strong>{activeProject.name}</strong></p>}
      <div className="process-actions">
        <button type="button" className="secondary-action" onClick={onStartCalculation}>Перейти к расчёту <AppIcon name="arrow" size={16} /></button>
        <button type="button" className="secondary-action" onClick={onOpenCatalog}>Открыть библиотеку <AppIcon name="library" size={16} /></button>
      </div>
      {hasResult && <button type="button" className="process-return" onClick={onReturnToResult}>Вернуться к результату расчёта</button>}
    </div><div className="process-hero-mark" aria-hidden="true"><AppIcon name="process" size={82} /></div></section>

    <section className="service-assistant-workspace" aria-label="Диалог о сервисе">
      <div className="assistant-dialog panel">
        <header><span className="catalog-eyebrow">ПОМОЩНИК ПО СЕРВИСУ</span><h2>Чем помочь?</h2>
          <p>Здесь можно разобраться в разделах и результатах. Описание процесса для расчёта вводится в разделе «Расчёт».</p></header>
        <div className="service-assistant-starters" aria-label="Примеры вопросов">
          {knowledge.starters.map((question) => <button key={question} type="button" className="secondary-action" onClick={() => send(null, question)} disabled={busy}>{question}</button>)}
        </div>
        <div className="assistant-turns" aria-live="polite">
          {!turns.length && <p className="assistant-empty">Выберите вопрос выше или напишите свой. Например: «Что такое зона?» или «Где скачать PDF?»</p>}
          {turns.map((turn, index) => <div className={`assistant-turn ${turn.role}`} key={`${index}-${turn.role}`}>
            <small>{turn.role === 'user' ? 'Вы' : 'Помощник'}</small><p>{turn.text}</p>
            {turn.role === 'assistant' && turn.actions?.length > 0 && <div className="service-assistant-links">
              {turn.actions.filter((action) => action.id !== 'result' || hasResult).map((action) =>
                <button key={action.id} type="button" className="secondary-action" onClick={() => follow(action.id)}>{action.label} <AppIcon name="arrow" size={14} /></button>)}
            </div>}
          </div>)}
        </div>
        <form className="assistant-form" onSubmit={send}>
          <label htmlFor="assistant-query">Вопрос о сервисе</label>
          <textarea id="assistant-query" ref={inputRef} rows="3" maxLength="400" value={input}
            onChange={(event) => setInput(event.target.value)} placeholder="Например: почему отчёт частичный?" />
          <div className="assistant-form-actions"><button type="submit" className="primary-action" disabled={busy || input.trim().length < 3}>{busy ? 'Отвечаем…' : 'Отправить'}</button></div>
          <small>{user ? 'Вопрос помогает найти раздел сервиса. Данные проекта не меняются.' : 'Справка доступна без регистрации. Данные проекта не меняются.'}</small>
        </form>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </section>
  </main>;
}
