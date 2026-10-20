import { useEffect, useRef, useState } from 'react';
import AppIcon from './AppIcon';

const API = import.meta.env.VITE_API_URL || '';

export default function RDAssistantWidget({ user }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef(null);
  const launcher = useRef(null);
  const wasOpen = useRef(false);
  const end = useRef(null);

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
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [turns, busy]);

  const send = async (event) => {
    event?.preventDefault();
    const question = message.trim();
    if (!user || busy || question.length < 2) return;
    setBusy(true); setError('');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 55000);
    try {
      const response = await fetch(`${API}/api/assistant/service`, { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ message: question, history: turns.slice(-8).map(({ role, text }) => ({ role, content: text })) }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Помощник временно недоступен. Повторите вопрос.');
      }
      if (body.schema_version !== 'service-assistant-chat-v2' || typeof body.reply !== 'string') throw new Error('Ответ помощника не удалось прочитать.');
      setTurns((current) => [...current, { role: 'user', text: question },
        { role: 'assistant', text: body.reply, sources: Array.isArray(body.sources) ? body.sources : [] }].slice(-20));
      setMessage('');
    } catch (failure) { setError(failure.name === 'AbortError' ? 'Ответ задерживается. Повторите вопрос.' : failure.message); }
    finally { clearTimeout(timeout); setBusy(false); input.current?.focus(); }
  };

  return <div className="rd-help">
    <button ref={launcher} type="button" className="rd-help-launcher" aria-label={open ? 'Закрыть ИИ-помощника' : 'Открыть ИИ-помощника'}
      aria-expanded={open} aria-controls="rd-help-dialog" title="Открыть помощника" onClick={() => setOpen((value) => !value)}><AppIcon name="assistant" size={30} /></button>
    {open && <section id="rd-help-dialog" className="rd-help-dialog" role="dialog" aria-modal="false" aria-label="ИИ-помощник"
      onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false); }}>
      <header><div><strong>ИИ-помощник</strong><small>Сервис · роботы · экономика</small></div>
        <button type="button" aria-label="Закрыть чат" onClick={() => setOpen(false)}>×</button></header>
      {!user ? <p>Для доступа к ИИ-помощнику зарегистрируйтесь или войдите в аккаунт.</p> : <><div className="rd-help-turns" role="log" aria-live="polite">
        {!turns.length && <p>Здравствуйте! Я помогу разобраться в сервисе, роботах и экономике. Задайте любой вопрос.</p>}
        {turns.map((turn, index) => <article key={`${index}-${turn.role}`} className={turn.role}>
          <small>{turn.role === 'user' ? 'Вы' : 'ИИ-помощник'}</small><p>{turn.text}</p>
          {!!turn.sources?.length && <details className="rd-help-sources"><summary>Материалы по теме</summary><ul>{turn.sources.map((source, sourceIndex) =>
            <li key={`${source.title}-${sourceIndex}`}>{source.url ? <a href={source.url}>{source.title}</a> : source.title}</li>)}</ul></details>}
        </article>)}
        {busy && <p className="rd-help-wait" role="status">Думаю над ответом…</p>}
        <div ref={end} />
      </div>
      <form onSubmit={send}><label className="sr-only" htmlFor="rd-help-question">Вопрос РД-помощнику</label>
        <textarea id="rd-help-question" ref={input} rows="2" maxLength="2000" value={message}
          onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); } }}
          placeholder="Напишите вопрос…" />
        <button type="submit" disabled={busy || message.trim().length < 2}>{busy ? '…' : 'Отправить'}</button></form>
      {error && <p className="rd-help-error" role="alert">{error}</p>}
      <small className="rd-help-note">Помощник использует Yandex Cloud. Не отправляйте личные или закрытые данные. Расчёты он не меняет.</small></>}
    </section>}
  </div>;
}
