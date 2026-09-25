import { useEffect, useMemo, useRef, useState } from 'react';
import {
  addZone,
  createDraft,
  createWarehouseDemoDraft,
  createWarehouseFileDraft,
  createNormalizationClient,
  confirmRoleAssumption,
  confirmProcessAssumption,
  removeZone,
  setRoleActive,
  updateProcess,
  updateRole,
  updateZone,
  validateDraft,
} from '../processRoleIntakeV2';
import { createCapacityAnalysisClient } from '../capacityAnalysisApi';
import { buildDemoCapacityRequest, demoCandidates, DEMO_MODELS, DEMO_PROFILES } from '../demoCapacityFlow';
import { readCsrfCookie } from '../persistenceApi';
import { toV2Draft } from '../assistantInterview';

const API = import.meta.env.VITE_API_URL || '';

const ROLE_LABELS = {
  forklift_driver: 'Оператор погрузчика', loader: 'Грузчик', storekeeper: 'Кладовщик', picker: 'Комплектовщик',
  sorter: 'Сортировщик', packer: 'Упаковщик', cleaner: 'Уборщик', inventory_worker: 'Сотрудник инвентаризации',
  baggage_handler: 'Обработчик багажа', trolley_operator: 'Оператор тележек', special_equipment_driver: 'Водитель спецтехники',
  terminal_cleaner: 'Уборщик терминала', perron_cleaner: 'Уборщик перрона', runway_inspector: 'Инспектор ВПП', security_guard: 'Сотрудник безопасности',
  passenger_assistant: 'Ассистент пассажиров', courier: 'Курьер', ramp_worker: 'Работник перрона', ground_support_worker: 'Наземное обслуживание',
  catering_worker: 'Работник пищеблока', laundry_worker: 'Работник прачечной', sanitary: 'Санитар', porter: 'Транспортировщик', lab_assistant: 'Лаборант',
  sterile_supply_worker: 'Сотрудник ЦСО', consumable_worker: 'Сотрудник снабжения', lab_result_courier: 'Курьер результатов',
};

const statusFor = (process, issues, response) => {
  if (!process.active) return ['Неактивен', 'text-slate-400'];
  const serverRefs = [
    ...(response?.errors || []).flatMap((item) => item.field_refs || [item.field]),
    ...(response?.required_inputs || []),
  ].filter(Boolean);
  if (serverRefs.some((ref) => ref.includes(process.blockId))) return ['Сервер: нужны данные', 'text-amber-700'];
  if (response?.normalized_processes?.some((item) => item.process_id === process.processId)) return ['Сервер: нормализован', 'text-green-700'];
  if (issues.some((item) => item.ref.startsWith(process.processId) && item.severity === 'BLOCKER')) return ['Нужны данные', 'text-red-600'];
  if (issues.some((item) => item.ref === process.processId && item.code === 'NO_FOT_BENEFIT')) return ['Без ФОТ-эффекта', 'text-amber-600'];
  return ['Готов к нормализации', 'text-green-600'];
};

export default function ProcessRoleIntakeV2({ objectType, importedFile, importedAssistant, activeProject, user, authChecked, projectChoices = [], projectStatus, onChooseProject, onOpenProjects, onOpenAccount, onNormalized, onCapacityResult }) {
  const [draft, setDraft] = useState(() => importedAssistant ? toV2Draft(importedAssistant)
    : importedFile ? createWarehouseFileDraft(importedFile.normalized, importedFile.imported) : createDraft(objectType));
  const [selectedZoneId, setSelectedZoneId] = useState(() => draft.zones[0].zoneId);
  const [expanded, setExpanded] = useState(null);
  const [result, setResult] = useState(null);
  const [state, setState] = useState('');
  const [error, setError] = useState('');
  const [positions, setPositions] = useState([]);
  const [catalogState, setCatalogState] = useState('loading');
  const [processId, setProcessId] = useState('');
  const [positionId, setPositionId] = useState('');
  const [exchangeSeconds, setExchangeSeconds] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [capacityBusy, setCapacityBusy] = useState(false);
  const [focusIssue, setFocusIssue] = useState('');
  const latestRevision = useRef(draft.inputRevision);
  const normalizationClient = useRef(null);
  const capacityClient = useRef(createCapacityAnalysisClient());
  useEffect(() => {
    latestRevision.current = draft.inputRevision;
  }, [draft.inputRevision]);
  useEffect(() => {
    normalizationClient.current = createNormalizationClient(
      (url, options) => fetch(`${API}${url}`, options),
      '/api/v2/calculation-intake/normalize',
      () => latestRevision.current,
    );
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/api/catalog/models?calculation_participation=participating`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        setPositions(payload.items || []);
        setCatalogState('ready');
      })
      .catch((catalogError) => {
        if (catalogError.name !== 'AbortError') setCatalogState('error');
      });
    return () => controller.abort();
  }, []);

  const issues = useMemo(() => validateDraft(draft), [draft]);
  const fieldIssue = (ref) => issues.find((item) => item.ref === ref)
    || (result?.response?.input_revision === draft.inputRevision && result.response.errors?.find((item) => (item.field_refs || [item.field]).some((field) => field?.includes(ref))));
  const blockers = issues.filter((item) => item.severity === 'BLOCKER');
  const activeCount = draft.processes.filter((item) => item.active).length;
  const visibleProcesses = draft.processes.filter((item) => item.zoneId === selectedZoneId);
  const selectedZone = draft.zones.find((zone) => zone.zoneId === selectedZoneId) || draft.zones[0];
  const normalizedIsCurrent = result?.response?.input_revision === draft.inputRevision;
  const activeProcesses = normalizedIsCurrent
    ? result.response.normalized_processes.filter((item) => item.active &&
      item.process_id.startsWith(`${selectedZoneId}.`) &&
      ['TRANSPORT_CYCLE', 'DELIVERY_CYCLE', 'CLEANING_AREA'].includes(item.scope))
    : [];
  const selectedProcess = activeProcesses.find((item) => item.process_id === processId) || activeProcesses[0];
  const candidatePositions = demoCandidates(positions, selectedProcess?.scope);
  const selectedPosition = candidatePositions.find((item) => item.position_id === positionId);

  const normalize = async () => {
    if (blockers.length || activeCount === 0) {
      const issue = blockers[0];
      const process = draft.processes.find((item) => issue?.ref.startsWith(`${item.processId}.`));
      if (process) { setSelectedZoneId(process.zoneId); setExpanded(process.processId); }
      setFocusIssue(issue?.ref || '');
      setError(issue?.code === 'BATCH_REQUIRED'
        ? `Для «${process.label}» в зоне «${draft.zones.find((zone) => zone.zoneId === process.zoneId)?.label}» укажите, сколько единиц груза робот перевозит за один рейс.`
        : issue?.code === 'BATCH_CONFIRMATION_REQUIRED'
          ? `Подтвердите допущение о числе единиц за рейс для «${process.label}».`
          : 'Заполните отмеченное обязательное поле выбранного процесса и зоны.');
      return;
    }
    setState('loading');
    setError('');
    try {
      const normalized = await normalizationClient.current(draft);
      setResult(normalized);
      setProcessId(normalized.response.normalized_processes.find((item) => item.active &&
        ['TRANSPORT_CYCLE', 'DELIVERY_CYCLE', 'CLEANING_AREA'].includes(item.scope))?.process_id || '');
      setPositionId('');
      onNormalized?.(normalized);
      setState('ready');
    } catch (requestError) {
      if (requestError.code === 'STALE_INTAKE_RESPONSE') return;
      setError(requestError.message || 'Не удалось проверить ввод');
      setState('');
    }
  };
  useEffect(() => {
    if (!focusIssue) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const field = document.getElementById(`intake-${focusIssue}`);
      field?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      field?.focus({ preventScroll: true });
      setFocusIssue('');
    });
    return () => window.cancelAnimationFrame(frame);
  }, [focusIssue, expanded, selectedZoneId]);

  const runCapacity = async () => {
    setError('');
    setCapacityBusy(true);
    try {
      const payload = buildDemoCapacityRequest({
        normalized: result, projectId: activeProject?.id, processId: selectedProcess?.process_id,
        position: selectedPosition, exchangeSeconds, acknowledged,
        zone: draft.zones.find((item) => selectedProcess?.process_id.startsWith(`${item.zoneId}.`)),
      });
      const response = await capacityClient.current.create(payload, readCsrfCookie());
      if (latestRevision.current !== payload.input_revision) return;
      onCapacityResult?.(response, payload);
    } catch (runError) {
      if (runError.code !== 'STALE_CAPACITY_RESPONSE') setError(runError.message || 'Расчёт недоступен');
    } finally {
      setCapacityBusy(false);
    }
  };

  return (
    <aside className="w-[480px] border-l bg-white p-4 overflow-auto" aria-label="Процессы и роли">
      <header className="mb-3">
        <div className="flex justify-between gap-3 items-start">
          <div><h2 className="font-semibold">Процессы и роли</h2><details className="text-xs text-slate-500"><summary>Технические подробности черновика</summary>Версия ввода: {draft.inputRevision}</details></div>
          <span className="text-[10px] rounded bg-blue-50 text-blue-700 px-2 py-1">{draft.schemaVersion}</span>
        </div>
        <p className="text-xs text-slate-500 mt-2">Вводите исходные значения. Один расчёт относится к одному процессу в одной зоне; для других процессов создайте отдельные результаты. Единицы и производные величины проверяет сервер.</p>
        {objectType === 'retail' && <button type="button" className="mt-2 text-xs underline text-blue-700" onClick={() => {
          setDraft(createWarehouseDemoDraft());
          setSelectedZoneId(`zone.${draft.objectId}.main`);
          setExchangeSeconds('90');
          setAcknowledged(false);
          setResult(null);
          setError('');
        }}>Загрузить типовой склад организаторов</button>}
        {objectType === 'retail' && <p className="text-[11px] text-amber-800 mt-1">Типовой склад предлагает 1 паллету за рейс, плечо 120 м и обмен 90 сек. как отдельные допущения. Подтвердите единицы за рейс в процессе и зарплату gross в роли.</p>}
      </header>

      <section className="mb-4 rounded-xl border border-slate-600 p-3 text-xs" aria-label="Зоны">
        <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Зоны объекта</h3>
          <button type="button" className="underline text-blue-700" onClick={() => {
            const next = addZone(draft, objectType);
            setDraft(next); setSelectedZoneId(next.zones.at(-1).zoneId); setExpanded(null);
          }}>Добавить зону</button></div>
        <div className="mt-2 flex flex-wrap gap-2">{draft.zones.map((zone) => <button key={zone.zoneId} type="button"
          className={`rounded border px-2 py-1 ${zone.zoneId === selectedZoneId ? 'border-blue-600 text-blue-700' : 'border-slate-600'}`}
          onClick={() => { setSelectedZoneId(zone.zoneId); setExpanded(null); }}>{zone.label}</button>)}</div>
        <label className="mt-3 block">Название зоны<input className="mt-1 w-full rounded border p-2" value={selectedZone.label}
          onChange={(event) => setDraft((current) => updateZone(current, selectedZoneId, { label: event.target.value }))} /></label>
        <label className="mt-2 block">Ограничения зоны · проходы, пол, потоки<textarea className="mt-1 w-full rounded border p-2" rows="2"
          value={selectedZone.constraints} onChange={(event) => setDraft((current) => updateZone(current, selectedZoneId, { constraints: event.target.value }))} /></label>
        <p className="mt-2 text-amber-800">Ограничения здесь служат заметкой черновика. Проверка пригодности не учитывает их автоматически; перенесите их в обследование объекта. Нагрузка и маршрут ниже относятся только к выбранной зоне. Одинаковая роль общая для зон: изменение её численности или зарплаты видно в каждой зоне.</p>
        {selectedZoneId !== draft.zones[0].zoneId && <button type="button" className="mt-2 underline text-red-700" onClick={() => {
          setDraft((current) => removeZone(current, selectedZoneId)); setSelectedZoneId(draft.zones[0].zoneId); setExpanded(null);
        }}>Удалить эту зону из черновика</button>}
      </section>

      {!activeProject && <section className="mb-4 rounded-lg border border-amber-400/50 bg-[#2b281d] p-3 text-xs text-amber-100" aria-label="Проект для расчёта">
        <p className="font-semibold">Для расчёта парка нужен открытый проект</p>
        {!authChecked ? <p className="mt-1">Проверяем вход…</p> : !user ? <>
          <p className="mt-1">Гостевой ввод можно проверить, но сохранение расчёта и полная экономика доступны после входа.</p>
          <button type="button" className="mt-2 font-semibold text-lime-300 underline" onClick={onOpenAccount}>Войти или зарегистрироваться</button>
        </> : projectStatus === 'loading' ? <p className="mt-1">Восстанавливаем ваш проект…</p> : projectStatus === 'error' ? <>
          <p className="mt-1">Не удалось загрузить ваши проекты. Откройте список проектов и повторите попытку.</p>
          <button type="button" className="mt-2 font-semibold text-lime-300 underline" onClick={onOpenProjects}>Мои проекты</button>
        </> : projectChoices.length === 0 ? <>
          <p className="mt-1">У вас пока нет проекта.</p>
          <button type="button" className="mt-2 font-semibold text-lime-300 underline" onClick={onOpenProjects}>Создать проект</button>
        </> : <label className="mt-2 block font-semibold">Выберите проект
          <select className="mt-1 w-full rounded border border-amber-400/50 bg-[#1b2529] p-2 text-slate-100" value="" onChange={(event) => {
            const project = projectChoices.find((item) => item.id === event.target.value);
            if (project) onChooseProject(project);
          }}>
            <option value="">Выберите проект для сохранения расчёта</option>
            {projectChoices.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>}
      </section>}

      <div className="space-y-2">
        {visibleProcesses.map((process) => {
          const open = expanded === process.processId;
          const [status, statusClass] = statusFor(process, issues, result?.response);
          return (
            <section key={process.blockId} className={`border rounded-lg ${process.active ? 'border-blue-300' : 'border-slate-200'}`}>
              <div className="flex items-center gap-2 px-3 py-2">
                <input id={`active-${process.processId}`} type="checkbox" checked={process.active} onChange={(event) => setDraft((current) => updateProcess(current, process.processId, { active: event.target.checked, activationSource: 'USER' }))} />
                <label htmlFor={`active-${process.processId}`} className="flex-1 text-sm font-medium">{process.label}</label>
                <button type="button" aria-expanded={open} aria-controls={`panel-${process.processId}`} onClick={() => setExpanded(open ? null : process.processId)} className="text-xs text-blue-700">{open ? 'Свернуть' : 'Открыть'}</button>
              </div>
              <div className="px-3 pb-2 flex justify-between text-[10px]"><span>{process.scope}</span><span className={statusClass}>{status}</span></div>
              {open && <div id={`panel-${process.processId}`} className="border-t bg-slate-50 p-3 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <NumberField id={`intake-${process.processId}.demand`} label={`Объём, ${process.unit}`} value={process.demand} issue={fieldIssue(`${process.processId}.demand`)} hint="Для мощности робота; например 2000 в сутки. Пусто — неизвестно, 0 означает отсутствие процесса." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { demand: value }))} />
                  <NumberField label="Смен/сут" value={process.shifts} issue={fieldIssue(`${process.processId}.schedule`)} hint="Для доступного времени; например 2. Источник — график работы." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { shifts: value }))} />
                  <NumberField label="Часов/смена" value={process.hours} issue={fieldIssue(`${process.processId}.schedule`)} hint="Для доступного времени; например 8. Источник — график работы." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { hours: value }))} />
                  <NumberField label="Дней/год" value={process.days} issue={fieldIssue(`${process.processId}.schedule`)} hint="Для годовой загрузки; например 250. Источник — календарь работы." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { days: value }))} />
                  {['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) && <NumberField id={`intake-${process.processId}.distance`} label="Одностороннее плечо, м" value={process.distance} issue={fieldIssue(`${process.processId}.distance`)} onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { distance: value }))} />}
                  {['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) && <div className="col-span-3 rounded border border-amber-300 p-2"><NumberField id={`intake-${process.processId}.batch`} label={`Сколько ${process.quantityKind === 'PALLET' ? 'паллет' : 'единиц груза'} робот перевозит за один рейс?`} value={process.batch} issue={fieldIssue(`${process.processId}.batch`)} hint={`Для «${process.label}» в зоне «${selectedZone.label}». Объём ${process.demand || 'неизвестен'} ${process.unit}, плечо ${process.distance || 'неизвестно'} м. Укажите целое число; для своего процесса значение не подставляется.`} onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { batch: value }))} />
                    {process.fieldSources?.batch === 'ASSUMPTION' && <label className="mt-2 flex gap-2 text-xs text-amber-900"><input type="checkbox" checked={process.fieldConfirmations?.batch === true} onChange={(event) => event.target.checked && setDraft((current) => confirmProcessAssumption(current, process.processId, 'batch'))} />Подтверждаю допущение: {process.batch} паллета за рейс для типового склада</label>}</div>}
                </div>
                <fieldset><legend className="text-xs font-semibold">Роли</legend>
                  {process.roles.length === 0 ? <p className="text-xs text-slate-500 mt-1">Роль не требуется: ФОТ-эффект не рассчитывается.</p> : process.roles.map((roleCode) => {
                    const role = draft.roles.find((item) => item.roleCode === roleCode && item.processIds.includes(process.processId));
                    return <div key={roleCode} className="mt-2 border rounded bg-white p-2">
                      <label className="flex gap-2 text-xs"><input type="checkbox" checked={Boolean(role)} onChange={(event) => setDraft((current) => setRoleActive(current, process.processId, roleCode, event.target.checked))} />{ROLE_LABELS[roleCode] || roleCode}</label>
                      {role && <div className="grid grid-cols-2 gap-2 mt-2">
                        <NumberField label="Численность, чел." value={role.headcount} issue={fieldIssue(`${role.roleId}.headcount`)} hint="Для технической и трудовой модели; например 25. Источник — штатное расписание." onChange={(value) => setDraft((current) => updateRole(current, role.roleId, { headcount: value, headcountSource: 'USER' }))} />
                        <NumberField label="Зарплата gross, ₽/чел./мес." value={role.salary} issue={fieldIssue(`${role.roleId}.salary`)} hint="Для ФОТ и NPV; например 120000. Пусто — экономика неизвестна, 0 — подтверждённая бесплатная роль. Источник — ФОТ." onChange={(value) => setDraft((current) => updateRole(current, role.roleId, { salary: value, salarySource: 'USER' }))} />
                        {role.salarySource === 'ASSUMPTION' && !role.salaryConfirmed && <label className="col-span-2 text-[10px] text-amber-700"><input type="checkbox" className="mr-1" onChange={(event) => event.target.checked && setDraft((current) => confirmRoleAssumption(current, role.roleId))} />Подтверждаю это допущение для текущего ввода</label>}
                        {!role.salary && <p className="col-span-2 text-[10px] text-amber-700">Без месячной зарплаты до удержаний технический расчёт возможен, а экономика останется частичной.</p>}
                      </div>}
                    </div>;
                  })}
                </fieldset>
              </div>}
            </section>
          );
        })}
      </div>

      <div className="mt-3 text-xs" aria-live="polite">
        {blockers.length > 0 && <p className="text-red-600">Исправьте обязательные поля: {blockers.length}.</p>}
        {issues.some((item) => item.code === 'SALARY_REQUIRED') && <p className="text-amber-700">Для расчёта ФОТ нужна зарплата каждой активной роли.</p>}
        {error && <p className="text-red-600">{error}</p>}
        {result && <NormalizationTrace result={result} />}
      </div>
      <button type="button" disabled={state === 'loading' || activeCount === 0} onClick={normalize} className="w-full rounded-xl py-3 mt-3 text-sm font-semibold bg-blue-600 text-white disabled:bg-slate-200 disabled:text-slate-400">
        {state === 'loading' ? 'Проверяем…' : 'Проверить ввод'}
      </button>
      {normalizedIsCurrent && <section className="mt-4 border rounded-xl p-3 space-y-3" aria-label="Предварительный расчёт">
        <h3 className="text-sm font-semibold">Предварительный расчёт</h3>
        <p className="text-xs text-amber-800">Каждый сохранённый расчёт парка относится только к одному выбранному процессу в одной зоне. Отдельные парки и денежные эффекты нельзя складывать при общих роботах, ролях, межзональных потоках или расходах площадки.</p>
        <p className="text-xs text-amber-800">Демо-профиль не является паспортом изготовителя. Неизвестные проверки пригодности останутся в результате; число роботов не означает готовность к закупке.</p>
        {!activeProject && <p className="text-xs text-amber-800">Выберите проект в блоке выше, чтобы сохранить расчёт.</p>}
        {activeProcesses.length === 0 ? <p className="text-xs text-slate-600">Для этого процесса пока нет расчётной модели производительности.</p> : <>
          <label className="block text-xs">Процесс
            <select className="w-full border rounded px-2 py-1" value={selectedProcess?.process_id || ''} onChange={(event) => { setProcessId(event.target.value); setPositionId(''); }}>
              {activeProcesses.map((item) => <option key={item.process_id} value={item.process_id}>{draft.zones.find((zone) => item.process_id.startsWith(`${zone.zoneId}.`))?.label || 'Зона'} · {visibleProcesses.find((process) => item.process_id.endsWith(process.processId))?.label || 'Процесс'}</option>)}
            </select>
          </label>
          <label className="block text-xs">Модель из активного capacity-каталога
            <select className="w-full border rounded px-2 py-1" value={positionId} onChange={(event) => setPositionId(event.target.value)}>
              <option value="">Выберите модель</option>
              {candidatePositions.map((item) => <option key={item.position_id} value={item.position_id}>{DEMO_MODELS[item.organizer_id]} · позиция {item.source_row_number}</option>)}
            </select>
          </label>
          {catalogState === 'loading' && <p className="text-xs text-slate-600" role="status">Загружаем расчётные модели…</p>}
          {catalogState === 'error' && <p className="text-xs text-red-700" role="alert">Каталог расчётных моделей недоступен. Обновите страницу и повторите попытку.</p>}
          {catalogState === 'ready' && candidatePositions.length === 0 && <p className="text-xs text-amber-800" role="status">В активном каталоге нет подходящего авторского демо-профиля для этого процесса. Проверьте capacity-активацию.</p>}
          {selectedPosition && <DemoProfile profile={DEMO_PROFILES[selectedPosition.organizer_id]} />}
          {selectedProcess?.scope !== 'CLEANING_AREA' && <NumberField label="Погрузка + выгрузка за рейс, сек. (демо-допущение)" value={exchangeSeconds} onChange={setExchangeSeconds} />}
          {selectedProcess?.scope === 'CLEANING_AREA' && <p className="text-xs text-slate-600">Демо-допущение: одна уборка указанной площади в сутки.</p>}
          <label className="flex gap-2 text-xs text-amber-900"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />Подтверждаю, что данные типового объекта и непроверенные условия дают только предварительную оценку.</label>
          <button type="button" className="w-full rounded-xl py-2 bg-blue-600 text-white text-sm disabled:bg-slate-200 disabled:text-slate-400" disabled={capacityBusy || !selectedPosition || !acknowledged} onClick={activeProject ? runCapacity : () => setError('Сначала выберите сохраняемый проект в блоке выше.')}>{capacityBusy ? 'Считаем…' : activeProject ? 'Рассчитать и сохранить' : 'Сначала выберите проект'}</button>
        </>}
      </section>}
    </aside>
  );
}

function DemoProfile({ profile }) {
  if (!profile) return null;
  return <details className="rounded-xl border border-lime-400/50 border-l-4 bg-[#1c2b25] p-4 text-xs text-slate-100" open>
    <summary className="cursor-pointer font-semibold text-lime-300">Авторский демо-профиль · не техпаспорт изготовителя</summary>
    <p className="mt-3 leading-relaxed"><a className="underline text-lime-300 underline-offset-2" href={profile.sourceUrl} target="_blank" rel="noreferrer">{profile.sourceLabel} · опубликованные характеристики</a>: {profile.published}</p>
    {profile.conflictUrl && <p className="mt-2"><a className="underline text-lime-300 underline-offset-2" href={profile.conflictUrl} target="_blank" rel="noreferrer">Второй источник изготовителя с отличающейся скоростью</a></p>}
    <p className="mt-3 leading-relaxed"><strong className="text-lime-200">Допущения:</strong> {profile.assumptions}</p>
    <p className="mt-2 leading-relaxed"><strong className="text-lime-200">Неизвестно:</strong> {profile.unknown}</p>
    <p className="mt-3 border-t border-lime-400/30 pt-3 font-semibold leading-relaxed text-amber-300">Пригодность на объекте требует проверки. Результат не подтверждает готовность к внедрению.</p>
  </details>;
}

function NumberField({ id, label, value, onChange, issue, hint }) {
  return <label className="text-[11px] text-slate-600">{label}<input id={id} type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(issue)} className="w-full border rounded px-2 py-1 text-sm" />
    {hint && <small className="block">{hint}</small>}{issue && <small className="block text-red-700" role="alert">{issue.message || issue.code}: укажите допустимое значение или проверьте единицу.</small>}</label>;
}

function NormalizationTrace({ result }) {
  const response = result.response;
  return <details className="mt-2 border rounded p-2"><summary className="cursor-pointer font-semibold">Технические подробности проверки · {response.valid ? 'готово' : 'нужны данные'}</summary>
    <p>Версия ввода: {response.input_revision}</p>
    {response.required_inputs?.map((field) => <div key={field} className="text-amber-700">Нужно: {field}</div>)}
    {response.conversions?.map((node) => <div key={node.node_id} className="mt-1"><code>{node.field}</code>: raw {node.raw_value} {node.raw_unit} → normalized {node.normalized_value} {node.normalized_unit} <span className="text-slate-400">({node.provenance.source})</span></div>)}
  </details>;
}
