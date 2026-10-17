import { useEffect, useRef, useState } from 'react';
import knowledge from '../../../contracts/service-assistant-knowledge-v1.json' with { type: 'json' };

const API = import.meta.env.VITE_API_URL || '';

export default function RDAssistantWidget({ activeProject, onNavigate }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef(null);
  const launcher = useRef(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener('robodovod:open-help', show);
    return () => window.removeEventListener('robodovod:open-help', show);
  }, []);
  useEffect(() => {
    if (open) input.current?.focus();
    else if (wasOpen.current) launcher.current?.focus();
    wasOpen.current = open;
  }, [open]);

  const send = async (event, suggested = '') => {
    event?.preventDefault();
    const question = (suggested || message).trim();
    if (busy || question.length < 3) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/assistant/service`, { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: question }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || body.schema_version !== knowledge.version || !Array.isArray(body.actions)) {
        throw new Error('Справка временно недоступна. Попробуйте ещё раз.');
      }
      setTurns((current) => [...current, { role: 'user', text: question },
        { role: 'assistant', text: body.reply, actions: body.actions }].slice(-20));
      setMessage('');
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); input.current?.focus(); }
  };

  const follow = (id) => {
    setOpen(false);
    onNavigate({ id: ({ demo: 'demo', calculation: 'calculation', catalog: 'library', projects: 'projects', result: 'results' })[id] || 'home' });
  };
  return <div className="rd-help">
    <button ref={launcher} type="button" className="rd-help-launcher" aria-label={open ? 'Закрыть РД-помощника' : 'Открыть РД-помощника'}
      aria-expanded={open} aria-controls="rd-help-dialog" onClick={() => setOpen((value) => !value)}>РД<span aria-hidden="true"> · ?</span></button>
    {open && <section id="rd-help-dialog" className="rd-help-dialog" role="dialog" aria-modal="false" aria-label="РД-помощник"
      onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false); }}>
      <header><div><strong>РД-помощник</strong><small>Помощь по сервису · {activeProject?.name || 'гостевой режим'}</small></div>
        <button type="button" aria-label="Закрыть чат" onClick={() => setOpen(false)}>×</button></header>
      <div className="rd-help-turns" role="log" aria-live="polite">
        {!turns.length && <><p>Спросите, как пройти оценку, проверить допущение или скачать отчёт.</p>
          <div className="rd-help-starters">{knowledge.starters.slice(0, 4).map((question) => <button type="button" key={question}
            onClick={() => send(null, question)} disabled={busy}>{question}</button>)}</div></>}
        {turns.map((turn, index) => <article key={`${index}-${turn.role}`} className={turn.role}>
          <small>{turn.role === 'user' ? 'Вы' : 'РД-помощник'}</small><p>{turn.text}</p>
          {turn.actions?.map((action) => <button type="button" key={action.id} onClick={() => follow(action.id)}>{action.label} →</button>)}
        </article>)}
      </div>
      <form onSubmit={send}><label className="sr-only" htmlFor="rd-help-question">Вопрос РД-помощнику</label>
        <textarea id="rd-help-question" ref={input} rows="2" maxLength="400" value={message}
          onChange={(event) => setMessage(event.target.value)} placeholder="Например: почему стоимость неполная?" />
        <button type="submit" disabled={busy || message.trim().length < 3}>{busy ? '…' : 'Отправить'}</button></form>
      {error && <p className="rd-help-error" role="alert">{error}</p>}
      <small className="rd-help-note">Помощник объясняет сервис. Расчёт и данные проекта он не меняет.</small>
    </section>}
  </div>;
}
