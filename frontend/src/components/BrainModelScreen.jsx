import { useEffect, useMemo, useState } from 'react';
import { BRAIN_FIELDS, capacityKpiDiff, makeBrainDraft, profileInputDiff } from '../brainProfile';
import { buildDemoCapacityRequest, brainCandidates, DEMO_MODELS } from '../demoCapacityFlow';
import { readCsrfCookie } from '../persistenceApi';
import EconomicsInputsV2 from './EconomicsInputsV2';
import EvidenceExportPanel from './EvidenceExportPanel';
import CapacityResultsTrace from './CapacityResultsTrace';
import PartialEconomicsResult from './PartialEconomicsResult';
import CommercialScenariosV2 from './CommercialScenariosV2';
import SavedEconomicsEditor from './SavedEconomicsEditor';
import WarehouseChainPanel from './WarehouseChainPanel';
import CandidateComparisonPanel from './CandidateComparisonPanel';
import { isCommercialScenariosBundle } from '../commercialScenariosModel';

const API = import.meta.env.VITE_API_URL || '';
const labels = Object.fromEntries(BRAIN_FIELDS.map(([key, label]) => [key, label]));
const action = (projectId, route, body) => fetch(`${API}/api/brain/projects/${encodeURIComponent(projectId)}/${route}`, {
  method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
  body: JSON.stringify(body),
}).then(async (response) => {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
  return payload;
});

export default function BrainModelScreen({ project, user, onOpenProjects, onOpenAccount, onViewRun }) {
  const [record, setRecord] = useState(null);
  const [message, setMessage] = useState('');
  const [editing, setEditing] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [assumption, setAssumption] = useState(false);
  const [busy, setBusy] = useState(false);
  const [turnStartedAt, setTurnStartedAt] = useState(null);
  const [waitingSeconds, setWaitingSeconds] = useState(0);
  const [error, setError] = useState('');
  const [positions, setPositions] = useState([]);
  const [positionId, setPositionId] = useState('');
  const [processCode, setProcessCode] = useState('warehouse_receiving_shipping');
  const [capacity, setCapacity] = useState(null);
  const [economics, setEconomics] = useState(null);
  const [capacityRequest, setCapacityRequest] = useState(null);
  const [priorResult, setPriorResult] = useState(null);
  const [savedSource, setSavedSource] = useState(null);
  const [catalogDefaults, setCatalogDefaults] = useState(null);
  const profile = record?.profile;
  const pendingSince = turnStartedAt ?? (profile?.model_status === 'PENDING' ? Date.parse(profile.model_started_at || '') : null);
  const readiness = record?.readiness;
  const versions = record?.versions || [];
  const previous = versions.length > 1 ? versions.at(-2) : null;
  const diff = useMemo(() => profileInputDiff(previous, profile), [previous, profile]);
  const kpiDiff = useMemo(() => capacityKpiDiff(priorResult, capacity), [priorResult, capacity]);

  useEffect(() => {
    if (!project?.id) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/brain/projects/${encodeURIComponent(project.id)}`, { credentials: 'include', signal: controller.signal })
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((value) => { setRecord(value); setMessage(sessionStorage.getItem(`brain-draft:${project.id}`) || ''); if (value.profile?.selected_process) setProcessCode(value.profile.selected_process); })
      .catch((e) => { if (e.name !== 'AbortError') setError(e.message); });
    fetch(`${API}/api/catalog/defaults`, { signal: controller.signal }).then((r) => r.ok ? r.json() : null)
      .then(setCatalogDefaults).catch(() => {});
    return () => controller.abort();
  }, [project?.id]);

  useEffect(() => {
    if (pendingSince === null || !Number.isFinite(pendingSince)) return undefined;
    const timer = window.setInterval(() => setWaitingSeconds(Math.max(0, Math.floor((Date.now() - pendingSince) / 1000))), 250);
    return () => window.clearInterval(timer);
  }, [pendingSince]);

  useEffect(() => {
    if (!project?.id || profile?.model_status !== 'PENDING' || busy) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${API}/api/brain/projects/${encodeURIComponent(project.id)}`, { credentials: 'include' });
        if (!response.ok) return;
        const value = await response.json();
        setRecord(value);
      } catch { /* Keep the saved pending state visible until the next poll. */ }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [project?.id, profile?.model_status, busy]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ calculation_participation: 'participating', object_kind: 'warehouse', process_code: processCode, include_unknown: 'true' });
    fetch(`${API}/api/catalog/models?${params}`, { signal: controller.signal })
      .then((r) => r.ok ? r.json() : { items: [] }).then((payload) => setPositions((payload.items || []).filter((p) => p.selection?.calculation_compatible))).catch(() => {});
    return () => controller.abort();
  }, [processCode]);

  const runAction = async (route, body, onSuccess) => {
    setBusy(true); setError('');
    try {
      const result = await action(project.id, route, body);
      if (result.profile?.profile_version > (record?.profile?.profile_version || 0)) {
        setPriorResult(capacity || priorResult);
        setCapacity(null); setEconomics(null); setCapacityRequest(null);
      }
      if (result.profile) setRecord((old) => ({ ...old, ...result, versions: result.profile.profile_version > (old?.profile?.profile_version || 0)
        ? [...(old?.versions || []), result.profile] : (old?.versions || []).map((version) => version.profile_version === result.profile.profile_version ? result.profile : version) }));
      onSuccess?.(result);
      return result;
    } catch (e) { setError(e.message || 'Не удалось сохранить черновик.'); return null; }
    finally { setBusy(false); }
  };

  const send = async (event) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || !profile) return;
    setWaitingSeconds(0); setTurnStartedAt(Date.now());
    const result = await runAction('turn', { expected_version: profile.profile_version, message: text });
    setTurnStartedAt(null);
    if (result && ['MODEL', 'LOCAL'].includes(result.model_status)) {
      setMessage(''); sessionStorage.removeItem(`brain-draft:${project.id}`);
    }
  };

  const retrySaved = async () => {
    setWaitingSeconds(0); setTurnStartedAt(Date.now());
    await runAction('retry', { expected_version: profile.profile_version });
    setTurnStartedAt(null);
  };

  const edit = async (field, value, provenance = 'user', confirmed = false) => {
    const result = await runAction('edit', { expected_version: profile.profile_version, field, value, provenance, confirmed });
    if (result) setEditing(null);
  };

  const confirm = async () => {
    const fields = Object.keys(profile.fields).filter((key) => !profile.fields[key].confirmed_by_user);
    const technical = ['object_type', 'process_type', 'operations_per_day', 'shifts_count', 'shift_hours', 'operating_days',
      ...(profile.fields.process_type?.value === 'transport' ? ['avg_distance_m', 'units_per_trip', 'exchange_seconds'] : ['cleaning_frequency_per_day'])];
    const readyAfter = supported && technical.every((key) => profile.fields[key]?.value);
    await runAction('confirm', { expected_version: profile.profile_version, fields, preflight: readyAfter });
  };

  const selectProcess = async (code) => {
    const result = await runAction('select-process', { expected_version: profile.profile_version, process_code: code });
    if (result) {
      setProcessCode(code); setCapacity(null); setEconomics(null); setCapacityRequest(null);
      setPositionId('');
    }
  };

  const calculate = async () => {
    setBusy(true); setError('');
    try {
      if (!profile.preflight_confirmed) throw new Error('Сначала подтвердите профиль и запуск расчёта.');
      const { request } = makeBrainDraft(profile, processCode);
      const normalizedResponse = await fetch(`${API}/api/v2/calculation-intake/normalize`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
      });
      const normalized = await normalizedResponse.json();
      if (!normalizedResponse.ok || !normalized.valid) throw new Error(normalized.errors?.[0]?.message || 'Проверьте исходные значения и единицы.');
      const normalizedProcess = normalized.normalized_processes.find((item) => item.active && item.process_code === processCode);
      const position = positions.find((item) => item.position_id === positionId);
      const payload = buildDemoCapacityRequest({ normalized: { request, response: normalized }, projectId: project.id,
        processId: normalizedProcess?.process_id, position, exchangeSeconds: profile.fields.exchange_seconds?.value,
        cleaningFrequency: profile.fields.cleaning_frequency_per_day?.confirmed_by_user ? profile.fields.cleaning_frequency_per_day.value : '',
        acknowledged: true, brainProfileVersion: profile.profile_version,
        zone: { zoneId: 'zone.draft.warehouse.main', label: profile.fields.zone_label?.value || 'Основная зона',
          constraints: profile.fields.zone_constraints?.value || '' } });
      const response = await fetch(`${API}/api/v2/capacity-analyses`, { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.issues?.[0]?.message || result.detail || 'Расчёт C11 недоступен.');
      const linked = await action(project.id, 'runs', { expected_version: profile.profile_version, run_id: result.run_id });
      setRecord((old) => ({ ...old, profile: linked.profile, readiness: linked.readiness,
        versions: old.versions.map((version) => version.profile_version === linked.profile.profile_version ? linked.profile : version) }));
      const previousRun = [...versions].reverse().filter((version) => version.selected_process === profile.selected_process)
        .flatMap((version) => (version.runs || []).filter((run) => run.run_kind === 'CAPACITY_ANALYSIS'))
        .find((run) => run.run_id !== result.run_id);
      if (previousRun) {
        try {
          const response = await fetch(`${API}/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(previousRun.run_id)}`, { credentials: 'include' });
          if (response.ok) setPriorResult((await response.json()).result_snapshot);
        } catch { setPriorResult(null); }
      }
      setCapacity(result); setCapacityRequest(payload); setEconomics(null);
      setSavedSource(economics?.id || versions.flatMap((version) => version.runs || []).filter((run) => run.run_kind === 'FULL_ANALYSIS').at(-1)?.run_id || null);
    } catch (e) { setError(e.message || 'Не удалось рассчитать.'); }
    finally { setBusy(false); }
  };

  const finishEconomics = async (run) => {
    setEconomics(run);
    try {
      const linked = await action(project.id, 'runs', { expected_version: profile.profile_version, run_id: run.id });
      setRecord((old) => ({ ...old, profile: linked.profile, readiness: linked.readiness,
        versions: old.versions.map((version) => version.profile_version === linked.profile.profile_version ? linked.profile : version) }));
    } catch (e) { setError(`Расчёт сохранён, но связь с профилем не обновилась: ${e.message}`); }
  };

  const candidates = brainCandidates(positions, processCode === 'warehouse_cleaning' ? 'CLEANING_AREA' : 'TRANSPORT_CYCLE');
  const supported = profile?.fields?.object_type?.value === 'retail' && ['transport', 'cleaning'].includes(profile?.fields?.process_type?.value);
  const scenario = project?.scenarios?.find((item) => item.slot === 'BASE');
  if (!user || !project) return <section className="panel p-6"><h1 className="text-2xl font-semibold">Моделирование процесса</h1>
    <p className="mt-3">Для сохранения диалога, версий профиля и расчётов нужен проект.</p>
    <button className="primary-action mt-3" onClick={user ? onOpenProjects : onOpenAccount}>{user ? 'Выбрать или создать проект' : 'Войти'}</button></section>;
  return <main className="mx-auto max-w-6xl space-y-5 p-4" aria-label="Моделирование процесса">
    <header><h1 className="text-2xl font-semibold">Моделирование процесса</h1><p>Расскажите о процессе своими словами. Brain предложит профиль; числа и допущения вы проверите до расчёта.</p>
      <p className="text-sm">Проект: {project.name} · версия профиля: {profile?.profile_version ?? '…'} · модель диалога: DeepSeek V4 Flash</p></header>
    {profile?.imported_workbook && <section className="panel p-4"><p>Книга сохранена полностью: зоны, процессы, роли, паспорт и экономика. Brain показывает первый процесс книги; для нескольких зон и процессов используйте форму расчёта. Коммерческие условия подтверждаются отдельно.</p>
      <a className="secondary-action" href="#calculation">Открыть все процессы в форме</a>
      <details><summary>Паспорт и источники книги</summary>{Object.entries(profile.imported_workbook.records).map(([sheet, records]) => <section key={sheet}><h3>{sheet}</h3>{Object.entries(records).flatMap(([id, fields]) => Object.entries(fields).map(([field, item]) => <p key={`${id}.${field}`}>{id}.{field}: {item.value ?? 'неизвестно'} {item.unit} · {item.status} · {item.source}</p>))}</section>)}</details></section>}
    {error && <p role="alert" className="rounded border border-red-400 p-3 text-red-700">{error}</p>}
    {profile && <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
      <section className="panel space-y-4 p-4" aria-label="Диалог Brain">
        <h2 className="text-lg font-semibold">Диалог</h2>
        <div className="max-h-80 space-y-2 overflow-auto" aria-live="polite">{versions.filter((item) => item.utterance && !item.utterance.startsWith('edit:')).map((item) => <div key={item.profile_version} className="rounded border p-2 text-sm"><strong>Вы:</strong> {item.utterance}<p><strong>Brain:</strong> {item.model_message || item.model_error || 'Поля сохранены.'}</p></div>)}</div>
        <p className="rounded bg-blue-50 p-3 text-sm">{readiness?.next_question?.text || 'Технический профиль собран. Проверьте и подтвердите поля; денежные данные можно добавить после C11.'}</p>
        {readiness?.next_question?.field === 'avg_distance_m' && <button className="secondary-action" disabled={busy} onClick={() => edit('avg_distance_m', '120', 'expert_assumption', false)}>Предложить 120 м как допущение</button>}
        {readiness?.next_question?.field === 'units_per_trip' && <button className="secondary-action" disabled={busy} onClick={() => edit('units_per_trip', '1', 'expert_assumption', false)}>Предложить 1 паллету за рейс как допущение</button>}
        {readiness?.next_question?.field === 'cleaning_frequency_per_day' && <button className="secondary-action" disabled={busy} onClick={() => edit('cleaning_frequency_per_day', '1', 'expert_assumption', false)}>Предложить одну уборку площади в сутки как допущение</button>}
        <form onSubmit={send} className="space-y-2"><label className="block text-sm">Ваше описание или ответ<textarea value={message} onChange={(event) => { setMessage(event.target.value); sessionStorage.setItem(`brain-draft:${project.id}`, event.target.value); }} rows="4" maxLength="2000" className="mt-1 w-full rounded border p-2" placeholder="Например: перевожу 220 паллет в день на 120 м" /></label>
          <button className="primary-action" disabled={busy || !message.trim()}>{busy ? 'Обрабатываем…' : 'Отправить'}</button></form>
        {(turnStartedAt !== null || profile.model_status === 'PENDING') && <p role="status" aria-live="polite" className="text-sm text-blue-800">{waitingSeconds < 5 ? 'Сообщение сохраняется и передаётся модели…' : `Ожидаем AI Studio ${waitingSeconds} с. Описание уже сохранено; можно вернуться после перезагрузки.`}</p>}
        {['FALLBACK', 'TIMEOUT'].includes(profile.model_status) && <div role="status" className="rounded border border-amber-500 p-3 text-sm text-amber-800"><p>{profile.model_status === 'TIMEOUT' ? 'Истекло время ожидания модели.' : 'Ответ модели не получен.'} {profile.model_error} Локально распознанные поля требуют подтверждения.</p><button className="secondary-action mt-2" disabled={busy} onClick={retrySaved}>Повторить сохранённое сообщение</button><p>Можно также изменить поля вручную справа. Черновик ответа не потерян.</p></div>}
        <p className="text-xs">Расход этого проекта: {record.usage?.turns || 0}/60 запросов, {record.usage?.tokens || 0}/120 000 токенов.</p>
      </section>
      <section className="panel space-y-3 p-4" aria-label="Профиль расчёта">
        <h2 className="text-lg font-semibold">Профиль расчёта</h2>
        {catalogDefaults?.defaults?.length > 0 && <div className="rounded border p-3"><p>Нормы каталога {catalogDefaults.catalog_code}: это допущения, требующие вашего подтверждения.</p>
          {catalogDefaults.defaults.map((norm) => <button key={norm.key} className="secondary-action mr-2" disabled={busy || profile.fields[norm.key]?.confirmed_by_user}
            onClick={() => runAction('catalog-default', { expected_version: profile.profile_version, catalog_code: catalogDefaults.catalog_code, field: norm.key })}>
            Предложить {labels[norm.key] || norm.key}: {norm.value} {norm.unit}</button>)}</div>}
        <p className="text-sm">Зона — отдельный поток или маршрут. Выберите «Основная зона», «Приёмка», «Отгрузка» или укажите другое название.</p>
        <div className="max-h-[560px] space-y-2 overflow-auto">{BRAIN_FIELDS.map(([key, label, unit, kind, options]) => {
          const field = profile.fields[key];
          const shownUnit = key === 'operations_per_day' && profile.fields.process_type?.value === 'cleaning' ? 'м²/сутки' : unit;
          return <div key={key} className="rounded border p-2 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{label}</strong><span>{field?.confirmed_by_user ? field.provenance === 'expert_assumption' ? 'Принятое допущение' : 'Принято' : field ? 'Нужно подтвердить' : 'Нужно уточнить'}</span></div>
            {editing === key ? <div className="mt-2 flex flex-wrap gap-2">{kind === 'choice' ? <select value={editValue} onChange={(e) => setEditValue(e.target.value)} className="rounded border p-1"><option value="">Выберите</option>{options.map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select>
              : key === 'zone_label' ? <select value={editValue} onChange={(e) => setEditValue(e.target.value)} className="rounded border p-1"><option value="">Выберите</option>{['Основная зона', 'Приёмка', 'Отгрузка', 'Другое'].map((name) => <option key={name}>{name}</option>)}</select>
                : <input aria-label={label} className="rounded border p-1" value={editValue} onChange={(e) => setEditValue(e.target.value)} />}
              <label><input type="checkbox" checked={assumption} onChange={(e) => setAssumption(e.target.checked)} /> Допущение</label>
              <button className="secondary-action" disabled={busy} onClick={() => edit(key, editValue, assumption ? 'expert_assumption' : 'user', true)}>Сохранить и подтвердить</button></div>
              : <><p>{field ? `${options?.find(([value]) => value === field.value)?.[1] || field.value} ${shownUnit || ''}` : '—'}</p>{field && <small>Источник: {field.provenance === 'expert_assumption' ? 'сценарное допущение' : field.raw_text?.startsWith('edit:') || field.raw_text === field.value ? 'ручной ввод' : 'слова пользователя'}{field.raw_text && field.raw_text !== field.value ? ` · ${field.raw_text}` : ''}</small>}
                <button className="ml-2 underline" onClick={() => { setEditing(key); setEditValue(field?.value || ''); setAssumption(field?.provenance === 'expert_assumption'); }}>Исправить</button></>}</div>;
        })}</div>
        {diff.length > 0 && <details><summary>Изменения с прошлой версии</summary>{diff.map(({ key, from, to }) => <p key={key} className="text-sm">{labels[key] || key}: {from} → {to}</p>)}</details>}
        <p className="text-sm">Техника: {readiness?.technical?.ready ? 'готово' : `нужны ${readiness?.technical?.missing?.map((key) => labels[key] || key).join(', ')}`}.</p>
        <p className="text-sm">Труд: {readiness?.labour?.ready ? 'готово' : `нужны ${readiness?.labour?.missing?.map((key) => labels[key] || key).join(', ')}`}.</p>
        <p className="text-sm">Покупка и аренда: условия и пять отдельных подтверждений проверяются в экономической форме после C11.</p>
        <div className="rounded border border-amber-300 p-3 text-sm"><strong>Перед расчётом</strong><p>Подтверждаются только видимые значения этой версии. Выбранная модель и обмен за рейс — сценарные данные; пригодность и закупка требуют проверки.</p>
          <button className="primary-action mt-2" disabled={busy || !Object.keys(profile.fields).length} onClick={confirm}>Подтвердить профиль</button></div>
      </section></div>}
    {profile && <section className="panel space-y-3 p-4" aria-label="Расчёт и результат"><h2 className="text-lg font-semibold">Рассчитать и пересчитать</h2>
      {profile.active_processes?.length > 1 && <div className="text-sm"><p>В профиле несколько процессов. Для каждого запускается отдельный run; парки и эффекты не складываются.</p>
        <ul className="mt-2 list-disc pl-5">{profile.active_processes.map((code) => <li key={code}>{code === 'warehouse_receiving_shipping' ? 'Перевозка паллет' : code === 'warehouse_cleaning' ? 'Уборка' : code}: {['warehouse_receiving_shipping', 'warehouse_cleaning'].includes(code) ? code === profile.selected_process ? readiness?.technical?.ready ? 'готов к C11' : 'нужны данные отдельного процесса' : profile.process_fields?.[code] ? 'профиль сохранён отдельно' : 'нужны данные отдельного процесса' : 'описан без поддержанной формулы'}</li>)}</ul></div>}
      {!supported && <p className="text-amber-800">Описанный процесс сохранён. Для него пока нет поддержанной формулы C11 или подтверждённого типа объекта; парк и NPV не выводятся.</p>}
      {profile.active_processes?.length > 1 && <label className="block text-sm">Выбрать отдельный процесс<select value={processCode} onChange={(e) => selectProcess(e.target.value)} className="mt-1 w-full rounded border p-2" disabled={busy}>
        {profile.active_processes.map((code) => <option key={code} value={code}>{code === 'warehouse_receiving_shipping' ? 'Перевозка паллет' : code === 'warehouse_cleaning' ? 'Уборка' : code} · отдельный профиль</option>)}</select></label>}
      {supported && <>
        <label className="block text-sm">Модель из активного расчётного каталога<select value={positionId} onChange={(e) => setPositionId(e.target.value)} className="mt-1 w-full rounded border p-2"><option value="">Выберите модель</option>{candidates.map((item) => <option key={item.position_id} value={item.position_id}>{DEMO_MODELS[item.organizer_id] || `${item.manufacturer} · ${item.name}`} · позиция {item.source_row_number}</option>)}</select></label>
        <p className="text-xs">Модель предлагается из действующего каталога; сервер заново проверяет пригодность и доступность расчёта.</p>
        <button className="primary-action" disabled={busy || !readiness?.technical?.ready || !profile.preflight_confirmed || !positionId} onClick={calculate}>{capacity ? 'Пересчитать как новый run' : 'Рассчитать и сохранить'}</button></>}
      {capacity && <><CapacityResultsTrace response={capacity} zoneContext={capacityRequest?.zone_context} /><CandidateComparisonPanel key={`comparison:${capacity.run_id}`} project={project} capacityRunId={capacity.run_id} /><p className="text-sm">Без подтверждённой зарплаты и условий ниже экономический результат останется частичным.</p>
        {scenario && <EconomicsInputsV2 key={`economics-inputs:${capacity.run_id}`} capacityRequest={capacityRequest} capacityRunId={capacity.run_id} project={project} onComplete={finishEconomics} sourceRunId={savedSource} />}
        <EvidenceExportPanel key={`capacity-export:${capacity.run_id}`} projectId={project.id} runId={capacity.run_id} />
        <button className="secondary-action" onClick={() => onViewRun({ id: capacity.run_id, run_kind: 'CAPACITY_ANALYSIS', input_snapshot: capacityRequest, result_snapshot: capacity }, capacityRequest)}>Открыть 2D/3D и полный технический результат</button></>}
      {economics && <>{isCommercialScenariosBundle(economics.result_snapshot)
        ? <><CommercialScenariosV2 key={economics.id} bundle={economics.result_snapshot} scenarioSpec={economics.scenario_spec_snapshot} projectName={project?.name} capacityRunId={capacity.run_id}
            onRestart={() => { setCapacity(null); setEconomics(null); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
            onRecalculate={() => { const summary = [...document.querySelectorAll('summary')].find((item) => item.textContent.includes('Изменить допущение и создать новый расчёт'));
              summary?.parentElement?.setAttribute('open', ''); summary?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }} />
          <SavedEconomicsEditor key={`economics-editor:${economics.id}`} project={project} run={economics} onComplete={finishEconomics} /></>
        : <PartialEconomicsResult result={economics.result_snapshot} run={economics} project={project} onComplete={finishEconomics} />}
        <EvidenceExportPanel key={`economics-export:${economics.id}`} projectId={project.id} runId={economics.id} /></>}
      {capacity && priorResult && <details><summary>Сравнение с предыдущим сохранённым результатом</summary>
        {kpiDiff.length ? kpiDiff.map((item) => <p key={item.key} className="text-sm">{item.label}: {item.from} → {item.to}</p>)
          : <p className="text-sm">Доступные технические KPI не изменились.</p>}</details>}
      {profile?.runs?.length > 0 && <div className="text-xs">Связанные сохранённые runs: {profile.runs.map((item) => <span key={item.run_id} className="mr-3">{item.run_kind}: {item.run_id} <a className="underline" href={`/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(item.run_id)}/exports/report-preview.pdf`} target="_blank" rel="noreferrer">PDF</a></span>)}</div>}
      {versions.flatMap((version) => (version.profile_version === profile.profile_version ? [] : (version.runs || []).map((run) => ({ ...run, version: version.profile_version })))).length > 0 &&
        <details><summary>Отчёты прошлых версий</summary>{versions.flatMap((version) => (version.profile_version === profile.profile_version ? [] : (version.runs || []).map((run) => ({ ...run, version: version.profile_version })))).map((run) =>
          <p key={`${run.version}-${run.run_id}`} className="text-sm">Версия {run.version} · {run.run_kind} · <a className="underline" href={`/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(run.run_id)}/exports/report-preview.pdf`} target="_blank" rel="noreferrer">PDF</a></p>)}</details>}
    </section>}
    {profile?.fields?.object_type?.value === 'retail' && <WarehouseChainPanel project={project} suggestedTransport={
      profile.fields.process_type?.value === 'transport' ? {
        demand: profile.fields.operations_per_day?.value, shifts: profile.fields.shifts_count?.value,
        hours: profile.fields.shift_hours?.value, days: profile.fields.operating_days?.value,
        zone: profile.fields.zone_label?.value || 'Основная зона',
        source: profile.fields.operations_per_day?.provenance === 'expert_assumption' ? 'EXPERT_ASSUMPTION' : 'USER',
      } : null} />}
  </main>;
}
