import { useEffect, useMemo, useRef, useState } from 'react';
import {
  addZone,
  confirmFacilityArea,
  createDraft,
  loadConfirmedTypicalObjectDraft,
  createWarehouseFileDraft,
  createNormalizationClient,
  confirmRoleAssumption,
  confirmProcessAssumption,
  removeZone,
  setRoleActive,
  updateProcess,
  updateFacility,
  updateRole,
  updateZone,
  validateDraft,
} from '../processRoleIntakeV2';
import { createCapacityAnalysisClient } from '../capacityAnalysisApi';
import { buildDemoCapacityRequest, demoCandidates, DEMO_MODELS, DEMO_PROFILES } from '../demoCapacityFlow';
import { catalogDiagnostics, recommendedCandidates } from '../candidateRecommendation';
import { readCsrfCookie } from '../persistenceApi';
import PickingStudy from './PickingStudy';
import PreliminaryCandidateSummary from './PreliminaryCandidateSummary';
import ObjectConstraints from './ObjectConstraints';
import { calculateOperationBatch } from '../operationBatch';
import { toV2Draft } from '../assistantInterview';
import { workbookDraft, confirmWorkbookDraft } from '../projectWorkbook';

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
const CAPACITY_STATUS_LABELS = { COMPLETE:'Парк рассчитан', WITH_ASSUMPTIONS:'Предварительный парк; условия требуют проверки',
  BLOCKED:'Парк заблокирован', NOT_APPLICABLE:'Формула неприменима' };

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

export default function ProcessRoleIntakeV2({ objectType, importedFile, importedAssistant, activeProject, initialFacilityContext, initialDraft, initialNormalized, onDraftChange, user, authChecked, projectChoices = [], projectStatus, onChooseProject, onOpenProjects, onOpenAccount, onNormalized, onCapacityResult }) {
  const [draft, setDraft] = useState(() => {
    if (importedAssistant) return toV2Draft(importedAssistant);
    if (initialDraft?.objectKind === { retail: 'WAREHOUSE', airport: 'AIRPORT', clinic: 'CLINIC' }[objectType]) return initialDraft;
    if (importedFile) return importedFile.normalized?.schema_version === 'project-workbook-v1' ? workbookDraft(importedFile.normalized)
      : createWarehouseFileDraft(importedFile.normalized, importedFile.imported);
    const fresh = createDraft(objectType);
    if (!initialFacilityContext) return fresh;
    return updateFacility(fresh, { totalArea: initialFacilityContext.total_area?.value || '',
      activeArea: initialFacilityContext.active_area?.value || '',
      fieldSources: { totalArea: initialFacilityContext.total_area?.source || 'USER',
        activeArea: initialFacilityContext.active_area?.source || 'USER' },
      fieldConfirmations: { totalArea: initialFacilityContext.total_area?.confirmed || false,
        activeArea: initialFacilityContext.active_area?.confirmed || false } });
  });
  const [selectedZoneId, setSelectedZoneId] = useState(() => draft.zones[0].zoneId);
  const [expanded, setExpanded] = useState(null);
  const [result, setResult] = useState(initialNormalized || null);
  const [state, setState] = useState('');
  const [error, setError] = useState('');
  const [positions, setPositions] = useState([]);
  const [catalogState, setCatalogState] = useState('loading');
  const [comparison, setComparison] = useState(null);
  const [comparisonState, setComparisonState] = useState('');
  const [processId, setProcessId] = useState('');
  const [positionId, setPositionId] = useState('');
  const [exchangeSeconds, setExchangeSeconds] = useState(draft.processes.find((item) => item.active)?.exchangeSeconds || '');
  const [cleaningFrequency, setCleaningFrequency] = useState(draft.processes.find((item) => item.active)?.cleaningFrequency ?? '1');
  const [acknowledged, setAcknowledged] = useState(false);
  const [capacityBusy, setCapacityBusy] = useState(false);
  const [focusIssue, setFocusIssue] = useState('');
  const [pickingCatalog, setPickingCatalog] = useState(null);
  const [pickingCatalogError, setPickingCatalogError] = useState('');
  const [operationBatch, setOperationBatch] = useState(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchProgress, setBatchProgress] = useState('');
  const [batchError, setBatchError] = useState('');
  const batchGuard = useRef(false);
  const batchAttempt = useRef(null);
  const latestRevision = useRef(draft.inputRevision);
  const normalizationClient = useRef(null);
  const capacityClient = useRef(createCapacityAnalysisClient());
  useEffect(() => {
    latestRevision.current = draft.inputRevision;
    onDraftChange?.(draft);
  }, [draft, onDraftChange]);
  useEffect(() => {
    normalizationClient.current = createNormalizationClient(
      (url, options) => fetch(`${API}${url}`, options),
      '/api/v2/calculation-intake/normalize',
      () => latestRevision.current,
    );
  }, []);


  const issues = useMemo(() => validateDraft(draft, { requireFacilityAreas: true }), [draft]);
  const fieldIssue = (ref) => issues.find((item) => item.ref === ref)
    || (result?.response?.input_revision === draft.inputRevision && result.response.errors?.find((item) => (item.field_refs || [item.field]).some((field) => field?.includes(ref))));
  const blockers = issues.filter((item) => item.severity === 'BLOCKER');
  const activeCount = draft.processes.filter((item) => item.active).length;
  const visibleProcesses = draft.processes.filter((item) => item.zoneId === selectedZoneId);
  const selectedZone = draft.zones.find((zone) => zone.zoneId === selectedZoneId) || draft.zones[0];
  const normalizedIsCurrent = result?.response?.input_revision === draft.inputRevision;
  const activeProcesses = normalizedIsCurrent
    ? result.response.normalized_processes.filter((item) => item.active &&
      item.process_id.startsWith(`${selectedZoneId}.`))
    : [];
  const selectedProcess = activeProcesses.find((item) => item.process_id === processId) || activeProcesses[0];
  const allActiveProcesses = normalizedIsCurrent ? result.response.normalized_processes.filter((item) => item.active) : [];
  useEffect(() => {
    if (!activeProject?.id) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/v2/projects/${encodeURIComponent(activeProject.id)}/operation-batches`,
      { credentials: 'include', signal: controller.signal })
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then(body => { if (!controller.signal.aborted) setOperationBatch(body.items?.[0] || null); })
      .catch(reason => { if (reason.name !== 'AbortError') setBatchError('Не удалось открыть сохранённую сводку операций.'); });
    return () => controller.abort();
  }, [activeProject?.id]);
  const pickingRows = pickingCatalog?.capabilities?.rows?.filter((item) => item.code === 'picking_lines' || item.code === 'picking_items') || [];
  const pickingCandidates = [...new Map(pickingRows.flatMap((item) => item.candidates || []).map((item) => [item.position_id, item])).values()];
  useEffect(() => {
    if (!selectedProcess) return undefined;
    const controller = new AbortController();
    const params = new URLSearchParams({ object_kind: selectedProcess.object_kind.toLowerCase(), process_code: selectedProcess.process_code });
    if (selectedProcess.item_mass?.status === 'KNOWN') params.set('max_payload_kg', selectedProcess.item_mass.normalized_value);
    fetch(`${API}/api/v2/capacity-catalog/positions?${params}`, { signal: controller.signal })
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((payload) => { setPositions(payload.items || []); setComparison(null); setComparisonState(''); setCatalogState('ready'); })
      .catch((e) => { if (e.name !== 'AbortError') { setPositions([]); setCatalogState('error'); } });
    return () => controller.abort();
  }, [selectedProcess]);
  useEffect(() => {
    if (selectedProcess?.process_code !== 'warehouse_picking' || !activeProject?.id) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/warehouse-chain/projects/${encodeURIComponent(activeProject.id)}`,
      { credentials: 'include', signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then((data) => { setPickingCatalog(data); setPickingCatalogError(''); })
      .catch((reason) => { if (reason.name !== 'AbortError') { setPickingCatalog(null); setPickingCatalogError('Не удалось получить варианты для комплектации из активного каталога.'); } });
    return () => controller.abort();
  }, [activeProject?.id, selectedProcess?.process_code]);
  const allCandidatePositions = demoCandidates(positions, selectedProcess?.scope);
  const candidatePositions = allCandidatePositions.filter(item => comparison?.candidates?.find(row => row.position_id === item.position_id)?.status !== 'EXCLUDED');
  const selectedPosition = candidatePositions.find((item) => item.position_id === positionId);
  const rankedCandidates = recommendedCandidates(comparison, positions);
  const diagnostics = catalogDiagnostics(positions, comparison);
  const invalidateComparison = () => { setComparison(null); setComparisonState(''); };
  useEffect(() => {
    if (!selectedProcess || !activeProject?.id || !acknowledged) return undefined;
    const candidates = demoCandidates(positions, selectedProcess.scope);
    if (!candidates.length) return undefined;
    let capacityRequest;
    try {
      capacityRequest = buildDemoCapacityRequest({
        normalized: result, projectId: activeProject.id, processId: selectedProcess.process_id,
        position: candidates[0], exchangeSeconds, acknowledged, cleaningFrequency,
        zone: draft.zones.find((item) => selectedProcess.process_id.startsWith(`${item.zoneId}.`)),
      });
    } catch { return undefined; }
    const controller = new AbortController();
    fetch(`${API}/api/candidate-comparisons/preview`, {
      method: 'POST', credentials: 'include', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
      body: JSON.stringify({ capacity_request: capacityRequest }),
    })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
        return body;
      })
      .then((body) => {
        if (controller.signal.aborted || latestRevision.current !== capacityRequest.input_revision) return;
        const ranked = recommendedCandidates(body, candidates);
        setComparison(body);
        setPositionId((current) => candidates.some((item) => item.position_id === current && body.candidates.find(row => row.position_id === current)?.status !== 'EXCLUDED')
          ? current : ranked[0]?.position_id || '');
        setComparisonState('ready');
      })
      .catch((reason) => { if (reason.name !== 'AbortError') setComparisonState('error'); });
    return () => controller.abort();
  }, [selectedProcess, activeProject?.id, acknowledged, exchangeSeconds, cleaningFrequency, result, positions, draft.zones]);
  const choosePhysicalInputs = (raw) => {
    setExchangeSeconds(raw?.exchangeSeconds ?? '');
    setCleaningFrequency(raw?.cleaningFrequency ?? '1');
  };

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
      setProcessId(normalized.response.normalized_processes.find((item) => item.active)?.process_id || '');
      choosePhysicalInputs(draft.processes.find((item) => item.active && item.zoneId === selectedZoneId));
      setPositionId('');
      invalidateComparison();
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
        cleaningFrequency,
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

  const runBatch = async () => {
    if (batchGuard.current) return;
    batchGuard.current = true;
    setBatchBusy(true); setBatchError(''); setBatchProgress('');
    try {
      if (batchAttempt.current?.projectId !== activeProject?.id || batchAttempt.current?.revision !== draft.inputRevision) {
        batchAttempt.current = { projectId: activeProject?.id, revision: draft.inputRevision, batchId: crypto.randomUUID(), rows: [] };
      }
      const created = await calculateOperationBatch({
        fetcher: fetch, api: API, normalized: result, draft, projectId: activeProject?.id,
        acknowledged, csrf: readCsrfCookie(), batchId: batchAttempt.current.batchId,
        resumeOperations: batchAttempt.current.rows,
        onCheckpoint: rows => { batchAttempt.current.rows = rows; },
        onProgress: (done, total) => setBatchProgress(`${done} из ${total}`),
      });
      setOperationBatch(created);
    } catch (reason) { setBatchError(`Сводка не завершена: ${reason.message || 'ошибка запроса'}. Сохранённые одиночные расчёты остаются в истории проекта.`); }
    finally { batchGuard.current = false; setBatchBusy(false); }
  };
  const openSavedOperation = async item => {
    setBatchError('');
    try {
      const [capacityResponse, runResponse] = await Promise.all([
        fetch(`${API}/api/v2/capacity-analyses/${encodeURIComponent(item.run_id)}`, { credentials:'include' }),
        fetch(`${API}/api/projects/${encodeURIComponent(activeProject.id)}/analysis-runs/${encodeURIComponent(item.run_id)}`, { credentials:'include' }),
      ]);
      if (!capacityResponse.ok || !runResponse.ok) throw new Error('сохранённый расчёт недоступен');
      const [capacity, run] = await Promise.all([capacityResponse.json(), runResponse.json()]);
      if (run.checksums?.result !== item.result_sha256 || run.input_snapshot?.process?.process_id !== item.process_id) {
        throw new Error('контрольная сумма или процесс расчёта не совпадают со сводкой');
      }
      onCapacityResult?.(capacity, run.input_snapshot);
    } catch (reason) { setBatchError(`Не удалось открыть операцию: ${reason.message}`); }
  };

  return (
    <section className="w-full min-w-0 rounded-xl border bg-white p-4 md:p-6" aria-label="Процессы и роли">
      {draft.importPending && <section className="file-report"><p>Проверьте предложения книги, единицы, источники и допущения. Apply не подтверждает ввод для расчёта.</p>
        <button type="button" className="primary-action" onClick={() => setDraft(confirmWorkbookDraft(draft))}>Подтвердить входы книги для расчёта</button></section>}
      <header className="mb-3">
        <div className="flex justify-between gap-3 items-start">
          <div><h2 className="font-semibold">Объект, процессы и роли</h2></div>
        </div>
        <p className="text-xs text-slate-500 mt-2">Вводите исходные значения. Один расчёт относится к одному процессу в одной зоне; для других процессов создайте отдельные результаты. Единицы и производные величины проверяет сервер.</p>
        <button type="button" className="mt-2 typical-object-action" onClick={() => {
          const typical = loadConfirmedTypicalObjectDraft(objectType);
          setDraft(typical);
          setSelectedZoneId(typical.zones[0].zoneId);
          setExpanded(typical.processes.find((item) => item.active)?.processId);
          setExchangeSeconds(objectType === 'retail' ? '90' : objectType === 'clinic' ? '180' : '');
          setCleaningFrequency('1');
          setProcessId(''); setPositionId(''); invalidateComparison();
          setAcknowledged(true);
          setResult(null);
          setError('');
        }}>Загрузить типовой {objectType === 'retail' ? 'склад' : objectType === 'airport' ? 'аэропорт' : 'объект клиники'} организаторов</button>
        {objectType !== 'retail' && <p className="text-xs text-amber-800 mt-2">{objectType === 'airport'
          ? 'Из датасета: терминал 85 000 м², уборка 51 000 м², зарплата 65 000 ₽ gross. 30 уборщиков, 3×8 ч и одна уборка в сутки — допущения.'
          : 'Из датасета: 45 000 м², 1 950 порций/сутки, плечо 180 м, зарплата 52 000 ₽ gross. Активная зона 18 000 м², 6 сотрудников только доставки, 3×8 ч, 65 порций за рейс и обмен 180 с — допущения. Приготовление пищи, лифты и санитарные режимы отдельно не моделируются.'} Нажатие кнопки заполняет и подтверждает типовые значения для предварительной оценки.</p>}
        {objectType === 'retail' && <p className="text-[11px] text-amber-800 mt-1">Типовой склад использует 1 паллету за рейс, плечо 120 м и обмен 90 сек. как допущения. Нажатие кнопки заполняет и подтверждает типовые значения для предварительной оценки.</p>}
      </header>

      <section className="mb-4 rounded-xl border p-3" aria-label="Площадь объекта">
        <h3 className="font-semibold text-sm">{draft.facility?.name || activeProject?.name || 'Объект'} · площадь</h3>
        <p className="text-xs text-slate-600 mt-1">Общая и активная площадь описывают объект. Площадь уборки задаётся отдельно в нужном процессе и не заменяется этими полями.</p>
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[['totalArea', 'Общая площадь объекта'], ['activeArea', 'Активная площадь объекта']].map(([key, label]) =>
            <div key={key} className="rounded border p-2">
              <NumberField required id={`intake-facility.${key}`} label={`${label}, м² · обязательно`} value={draft.facility?.[key] || ''}
                issue={fieldIssue(`facility.${key}`)} onChange={(value) => setDraft((current) => updateFacility(current, { [key]: value }))} />
              <p className="text-xs text-slate-600 mt-1">Источник: {sourceLabel(draft.facility?.fieldSources?.[key])}. {draft.facility?.[key] ? 'Единица: м².' : 'Нет данных.'}</p>
              {draft.facility?.[key] && draft.facility?.fieldSources?.[key] !== 'USER' &&
                <label className="mt-1 flex items-start gap-2 text-xs"><input type="checkbox" checked={draft.facility?.fieldConfirmations?.[key] === true}
                  onChange={(event) => event.target.checked && setDraft((current) => confirmFacilityArea(current, key))} />Подтверждаю значение и источник</label>}
            </div>)}
        </div>
      </section>

      <section className="mb-4 rounded-xl border border-slate-600 p-3 text-xs" aria-label="Зоны">
        <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Зоны объекта</h3>
          <button type="button" className="underline text-blue-700" onClick={() => {
            const next = addZone(draft, objectType);
            setDraft(next); setSelectedZoneId(next.zones.at(-1).zoneId); setExpanded(null);
          }}>Добавить зону</button></div>
        <div className="mt-2 flex flex-wrap gap-2">{draft.zones.map((zone) => <button key={zone.zoneId} type="button"
          className={`rounded border px-2 py-1 ${zone.zoneId === selectedZoneId ? 'border-blue-600 text-blue-700' : 'border-slate-600'}`}
          onClick={() => { setSelectedZoneId(zone.zoneId); setProcessId(''); setPositionId(''); choosePhysicalInputs(draft.processes.find((item) => item.active && item.zoneId === zone.zoneId)); setExpanded(null); }}>{zone.label}</button>)}</div>
        <label className="mt-3 block">Название зоны<input className="mt-1 w-full rounded border p-2" value={selectedZone.label}
          onChange={(event) => setDraft((current) => updateZone(current, selectedZoneId, { label: event.target.value }))} /></label>
        <label className="mt-2 block">Ограничения зоны · проходы, пол, потоки<textarea className="mt-1 w-full rounded border p-2" rows="2"
          value={selectedZone.constraints} onChange={(event) => setDraft((current) => updateZone(current, selectedZoneId, { constraints: event.target.value }))} /></label>
        <ObjectConstraints zone={selectedZone} onChange={value => { invalidateComparison(); setDraft(current => updateZone(current, selectedZoneId, { objectConstraints: value })); }} />
        <p className="mt-2 text-amber-800">Подтверждённые структурированные требования применяются при подборе и расчёте. Нагрузка и маршрут относятся к выбранной зоне. Одинаковая роль общая для зон: изменение численности или зарплаты видно в каждой зоне.</p>
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

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
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
              <div className="px-3 pb-2 flex justify-end text-xs"><span className={statusClass}>{status}</span></div>
              {open && <div id={`panel-${process.processId}`} className="border-t bg-slate-50 p-3 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  <NumberField id={`intake-${process.processId}.demand`} label={`Объём, ${process.unit}`} value={process.demand} issue={fieldIssue(`${process.processId}.demand`)} hint="Для мощности робота; например 2000 в сутки. Пусто — неизвестно, 0 означает отсутствие процесса." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { demand: value }))} />
                  <NumberField label="Смен/сут" value={process.shifts} issue={fieldIssue(`${process.processId}.schedule`)} hint="Для доступного времени; например 2. Источник — график работы." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { shifts: value }))} />
                  <NumberField label="Часов/смена" value={process.hours} issue={fieldIssue(`${process.processId}.schedule`)} hint="Для доступного времени; например 8. Источник — график работы." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { hours: value }))} />
                  <NumberField label="Дней/год" value={process.days} issue={fieldIssue(`${process.processId}.schedule`)} hint="Для годовой загрузки; например 250. Источник — календарь работы." onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { days: value }))} />
                  {['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) && <NumberField id={`intake-${process.processId}.distance`} label="Одностороннее плечо, м" value={process.distance} issue={fieldIssue(`${process.processId}.distance`)} onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { distance: value }))} />}
                  {['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) && <div className="sm:col-span-2 lg:col-span-3 rounded border border-amber-300 p-2"><NumberField id={`intake-${process.processId}.batch`} label={`Сколько ${process.quantityKind === 'PALLET' ? 'паллет' : 'единиц груза'} робот перевозит за один рейс?`} value={process.batch} issue={fieldIssue(`${process.processId}.batch`)} hint={`Для «${process.label}» в зоне «${selectedZone.label}». Объём ${process.demand || 'неизвестен'} ${process.unit}, плечо ${process.distance || 'неизвестно'} м. Укажите целое число; для своего процесса значение не подставляется.`} onChange={(value) => setDraft((current) => updateProcess(current, process.processId, { batch: value }))} />
                    {process.fieldSources?.batch === 'ASSUMPTION' && <label className="mt-2 flex gap-2 text-xs text-amber-900"><input type="checkbox" checked={process.fieldConfirmations?.batch === true} onChange={(event) => event.target.checked && setDraft((current) => confirmProcessAssumption(current, process.processId, 'batch'))} />Подтверждаю допущение: {process.batch} {process.quantityKind === 'PALLET' ? 'паллет' : process.quantityKind === 'PORTION' ? 'порций' : 'единиц груза'} за рейс для этого процесса</label>}</div>}
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
      {normalizedIsCurrent && <section className="mt-4 rounded-xl border p-3 text-xs" aria-label="Операции по зонам">
        <h3 className="font-semibold">Операции по зонам · {allActiveProcesses.length}</h3>
        <p className="mt-1">Можно рассчитать весь выбранный набор: для каждой операции система сохранит отдельный парк или причину отсутствия расчёта. Общую экономику проект получит после проверки совместного использования людей, парка и инфраструктуры.</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">{allActiveProcesses.map((process) => {
          const zone = draft.zones.find((item) => process.process_id.startsWith(`${item.zoneId}.`));
          const source = draft.processes.find((item) => item.processId === process.process_id);
          return <button key={process.process_id} type="button" className={`rounded border p-2 text-left ${selectedProcess?.process_id === process.process_id ? 'border-blue-500' : 'border-slate-500'}`}
            onClick={() => { setSelectedZoneId(zone?.zoneId || draft.zones[0].zoneId); setProcessId(process.process_id); setPositionId(''); invalidateComparison(); choosePhysicalInputs(source); }}>
            <strong>{zone?.label || 'Зона'} · {source?.label || process.process_code}</strong>
            <span className="block mt-1">{['TRANSPORT_CYCLE', 'DELIVERY_CYCLE', 'CLEANING_AREA'].includes(process.scope)
              ? 'Отдельный предварительный расчёт парка' : process.process_code === 'warehouse_picking'
                ? 'Варианты каталога и отдельная проверка комплектовки' : 'Операция описана; расчётной формулы пока нет'}</span>
          </button>;
        })}</div>
        <button type="button" className="primary-action mt-3" disabled={batchBusy || !activeProject?.id || !acknowledged} onClick={runBatch}>{batchBusy ? `Рассчитываем операции · ${batchProgress}` : 'Рассчитать все выбранные операции'}</button>
        {batchError && <p role="alert" className="text-red-700 mt-2">{batchError}</p>}
        {operationBatch?.project_id === activeProject?.id && <div className="mt-3 rounded border p-2" aria-label="Сохранённая сводка операций">
          <p><strong>Сводка версии {operationBatch.input_revision}</strong> · {operationBatch.status === 'PARTIAL' ? 'частичная' : 'все отдельные операции обработаны'} · {operationBatch.operations.length} операций.</p>
          <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left"><thead><tr><th>Зона и операция</th><th>Объём</th><th>Модель и парк</th><th>Состояние</th></tr></thead><tbody>{operationBatch.operations.map(item =>
            <tr key={item.process_id}><td>{item.zone_label} · {draft.processes.find(process => process.processId === item.process_id)?.label || item.process_code}</td><td>{item.demand.normalized_value ?? 'нет данных'} {item.demand.unit}</td>
              <td>{item.model_id || '—'} · {item.capacity?.recommended_fleet ?? '—'}</td><td>{item.blocker || CAPACITY_STATUS_LABELS[item.capacity_status] || item.status}{item.run_id && <button type="button" className="ml-2 underline" onClick={() => openSavedOperation(item)}>Открыть расчёт</button>}</td></tr>)}</tbody></table></div>
          <p className="mt-2 text-amber-800">Экономика проекта: {operationBatch.project_economics.reason}</p>
          <a className="underline" href={`${API}/api/v2/projects/${encodeURIComponent(activeProject.id)}/operation-batches/${encodeURIComponent(operationBatch.id)}/report.pdf`}>Скачать PDF этой сводки</a>
        </div>}
      </section>}
      {normalizedIsCurrent && <section className="preliminary-section mt-4 space-y-3" aria-label="Предварительный расчёт">
        <header className="preliminary-section-heading"><div><span className="preliminary-eyebrow">ШАГ 02 · МОДЕЛЬ И ПАРК</span><h3>Предварительный расчёт</h3></div><span className="preliminary-review-badge">Оценка, не допуск к закупке</span></header>
        <p className="preliminary-section-lead">Выберите операцию и модель. Парк сохраняется отдельно для каждой зоны и операции.</p>
        <details className="preliminary-scope"><summary>Границы расчёта и допущения</summary><p>Отдельные парки и денежные эффекты нельзя складывать при общих роботах, ролях, межзональных потоках или расходах площадки. Демо-профиль не является паспортом изготовителя; неизвестные проверки пригодности остаются в результате.</p></details>
        {!activeProject && <p className="text-xs text-amber-800">Выберите проект в блоке выше, чтобы сохранить расчёт.</p>}
        {activeProcesses.length === 0 ? <p className="text-xs text-slate-600">В выбранной зоне нет активных операций. Выберите зону и операцию в списке выше.</p>
          : selectedProcess?.scope === 'REFERENCE_ONLY' ? <div className="space-y-3 rounded-lg border border-amber-400 p-3 text-xs">
            <strong>{selectedZone.label} · {draft.processes.find((item) => item.processId === selectedProcess.process_id)?.label || selectedProcess.process_code}</strong>
            {selectedProcess.process_code === 'warehouse_picking' ? <>
              <p>Комплектовка не равна перевозке паллет. Ни погрузчик, ни мойщик не получают экономию комплектовщика. Ниже — возможные технологии из активного каталога для изучения, без подтверждённого расчёта парка или закупочной рекомендации.</p>
              {!activeProject && <p>Выберите проект, чтобы получить позиции активного каталога и проверить арифметику отбора.</p>}
              {pickingCatalogError && <p role="alert">{pickingCatalogError}</p>}
              {activeProject && !pickingCatalog && !pickingCatalogError && <p role="status">Ищем варианты комплектации в активном каталоге…</p>}
              {pickingCatalog && (pickingCandidates.length ? <ul className="list-disc pl-5 space-y-1">{pickingCandidates.map((candidate) =>
                <li key={candidate.position_id}>{candidate.name} · {({ ROBOT_ARM: 'роботизированный захват', ASRS_G2P: 'подача товара к человеку', PICK_ASSIST: 'помощь человеку', MOBILE_PICKER: 'мобильный робот-комплектовщик', OTHER_PICKING: 'другая технология комплектации' })[candidate.solution_family] || 'тип требует проверки'} · {candidate.maturity_status === 'RND' ? 'исследовательская разработка' : 'только сравнение'}; производительность отбора и пригодность на объекте требуют подтверждения.</li>)}</ul>
                : <p>В активном каталоге нет позиции с подтверждённым профилем отбора. Нужны паспорт робота или измеренная производительность и проверка условий объекта.</p>)}
              {pickingRows.some((item) => item.solution_families) && <p>Классы решений: роботизированный захват, подача товара к человеку (G2P/AS-RS), подсказки комплектовщику (Voice/Light). Последние два сами не выполняют захват товара.</p>}
              <PickingStudy key={selectedProcess.process_id} project={activeProject} process={selectedProcess} zone={selectedZone}
                pickerHeadcount={draft.roles.find((role) => role.roleCode === 'picker' && role.processIds.includes(selectedProcess.process_id))?.headcount || ''} />
            </> : <p>Операция сохранена во вводе, но для неё нет проверенной формулы парка. Каталожное совпадение не означает расчёт пригодности.</p>}
          </div> : <>
          <label className="block text-xs">Процесс
            <select className="w-full border rounded px-2 py-1" value={selectedProcess?.process_id || ''} onChange={(event) => { setProcessId(event.target.value); setPositionId(''); invalidateComparison(); choosePhysicalInputs(draft.processes.find((item) => item.processId === event.target.value)); }}>
              {activeProcesses.map((item) => <option key={item.process_id} value={item.process_id}>{draft.zones.find((zone) => item.process_id.startsWith(`${zone.zoneId}.`))?.label || 'Зона'} · {visibleProcesses.find((process) => item.process_id.endsWith(process.processId))?.label || 'Процесс'}</option>)}
            </select>
          </label>
          {comparisonState === 'error' && <p role="alert" className="preliminary-error">Автоматический подбор недоступен; позицию можно выбрать вручную. Проверки пригодности появятся в сохранённом расчёте.</p>}
          <PreliminaryCandidateSummary comparison={comparison} diagnostics={diagnostics} rankedCandidates={rankedCandidates} candidatePositions={candidatePositions}
            selectedPositionId={positionId} onSelect={setPositionId} />
          <label className="block text-xs">Модель из активного capacity-каталога
            <select className="w-full border rounded px-2 py-1" value={positionId} onChange={(event) => setPositionId(event.target.value)}>
              <option value="">Выберите модель</option>
              {candidatePositions.map((item) => <option key={item.position_id} value={item.position_id}>{DEMO_MODELS[item.organizer_id] || `${item.manufacturer || ''} · ${item.name}`} · позиция {item.source_row_number}{comparison?.candidates?.find((row) => row.position_id === item.position_id)?.technical_score ? ` · балл ${comparison.candidates.find((row) => row.position_id === item.position_id).technical_score}` : ''}{item.selection?.status === 'REQUIRES_CHECK' ? ' · требует проверки' : ''}</option>)}
            </select>
          </label>
          {positions.filter((item) => item.selection?.status === 'EXCLUDED' || item.maturity_status === 'RND' || !item.calculation_ready).length > 0 && <details className="text-xs rounded border p-2"><summary>Почему другие позиции не предложены</summary>
            <ul className="mt-1 list-disc pl-5">{positions.filter((item) => item.selection?.status === 'EXCLUDED' || item.maturity_status === 'RND' || !item.calculation_ready).map((item) => <li key={item.position_id}>{item.name}: {item.selection?.status === 'EXCLUDED' ? item.selection.reasons?.join('; ') : item.maturity_status === 'RND' ? 'исследовательская разработка; только сведения' : 'нет утверждённой формулы; только сведения'}.</li>)}</ul>
          </details>}
          {catalogState === 'loading' && <p className="text-xs text-slate-600" role="status">Загружаем расчётные модели…</p>}
          {catalogState === 'error' && <p className="text-xs text-red-700" role="alert">Каталог расчётных моделей недоступен. Обновите страницу и повторите попытку.</p>}
          {catalogState === 'ready' && candidatePositions.length === 0 && <p className="text-xs text-amber-800" role="status">Для этого процесса в активном каталоге нет расчётной рекомендации. Информационные позиции и причины показаны выше; парк не рассчитывается без утверждённой физической формулы.</p>}
          {selectedPosition && <DemoProfile profile={DEMO_PROFILES[selectedPosition.organizer_id]} />}
          {selectedProcess?.scope === 'DELIVERY_CYCLE' && selectedPosition?.calculation_profile === 'TRANSPORT_CYCLE_V1' && <p className="text-xs text-amber-800">Предварительная доставка рассчитана по транспортному циклу. Оснастка для питания, масса партии, лифты и санитарные условия требуют отдельной проверки; применимость модели в клинике не подтверждена.</p>}
          {['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(selectedProcess?.scope) && <NumberField label="Погрузка + выгрузка за рейс, сек. (демо-допущение)" value={exchangeSeconds} onChange={(value) => { setExchangeSeconds(value); setDraft(current => updateProcess(current, selectedProcess.process_id, { exchangeSeconds: value })); invalidateComparison(); }} />}
          {selectedProcess?.scope === 'CLEANING_AREA' && <NumberField label="Уборок указанной площади за сутки (сценарное допущение)" value={cleaningFrequency} onChange={(value) => { setCleaningFrequency(value); setDraft(current => updateProcess(current, selectedProcess.process_id, { cleaningFrequency: value })); invalidateComparison(); }} />}
          <label className="flex gap-2 text-xs text-amber-900"><input type="checkbox" checked={acknowledged} onChange={(event) => { setAcknowledged(event.target.checked); invalidateComparison(); }} />Подтверждаю, что данные типового объекта и непроверенные условия дают только предварительную оценку.</label>
          {!acknowledged && <p className="text-xs text-amber-800" role="status">Чтобы запустить расчёт, подтвердите предварительные допущения выше.</p>}
          {acknowledged && candidatePositions.length > 0 && !selectedPosition && <p className="text-xs text-amber-800" role="status">Выберите модель в списке выше. Расчёт можно запустить вручную, даже если автоматический подбор недоступен.</p>}
          <button type="button" className="w-full rounded-xl py-2 bg-blue-600 text-white text-sm disabled:bg-slate-200 disabled:text-slate-400" disabled={capacityBusy || !selectedPosition || !acknowledged} onClick={activeProject ? runCapacity : () => setError('Сначала выберите сохраняемый проект в блоке выше.')}>{capacityBusy ? 'Считаем…' : activeProject ? 'Рассчитать и сохранить' : 'Сначала выберите проект'}</button>
        </>}
      </section>}
    </section>
  );
}

function sourceLabel(source) {
  return { USER: 'ввод', FILE: 'файл', ORGANIZER: 'типовой датасет организаторов', ASSUMPTION: 'допущение', LLM: 'предложение помощника' }[source] || 'не указан';
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

function NumberField({ id, label, value, onChange, issue, hint, required = false }) {
  return <label className="text-[11px] text-slate-600">{label}<input id={id} required={required} aria-required={required} type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(issue)} className={`w-full border rounded px-2 py-1 text-sm ${issue ? 'border-red-500 bg-red-50' : ''}`} />
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
