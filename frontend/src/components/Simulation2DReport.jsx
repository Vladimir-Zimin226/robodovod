import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { SimulationApiSession } from '../simulationApi';
import {
  buildSimulationScene,
  createTimelineState,
  frameAt,
  hasCapacityWarning,
  parseSimulationBundle,
  reduceTimeline,
} from '../simulation2dModel';
import RobCraftFrame from './RobCraftFrame';
import Warehouse2DPlan from './Warehouse2DPlan';
import SimulationChainSetup from './SimulationChainSetup';
import { humanizePresentation, statusLabel } from '../presentation';
import { formatModelClock } from '../simulationDefaults';
import SavedPhysicalScenarios from './SavedPhysicalScenarios';
import { physicalInputs } from '../physicalScenario';
import { downloadSimulationSvg, visualExportMetadata } from '../simulationSvgExport';

const STATUS_LABELS = {
  STOPPED: 'Остановлено', RUNNING: 'Воспроизведение', PAUSED: 'Пауза',
};
const SLA_LABELS = {
  PASS: 'Норматив времени выполнен',
  FAIL: 'Норматив времени не выполнен',
  CONDITIONAL: 'Условный результат · модель неполна',
  NOT_EVALUATED: 'Норматив времени не оценён',
};

function number(value, suffix = '') {
  if (value === null || value === undefined) return 'нет данных';
  const parsed = Number(value);
  return `${Number.isFinite(parsed) ? new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(parsed) : value}${suffix}`;
}

function metric(label, value, detail, key) {
  return <div key={key} className="simulation-kpi"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

function path(points) {
  return points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
}

export default function Simulation2DReport({ request, initialReport = null, scenarios = null, analysisRunId = null }) {
  if (analysisRunId && request) return <SavedPhysicalScenarios key={`${request.tenant_id}:${request.project_id}:${analysisRunId}`} request={request} analysisRunId={analysisRunId}>
    {(activeRequest, activeRunId) => <SimulationPlayer key={`${activeRunId}:${activeRequest.request_id}`} request={activeRequest} analysisRunId={activeRunId} />}
  </SavedPhysicalScenarios>;
  return <SimulationPlayer key={request?.request_id} request={request} initialReport={initialReport} scenarios={scenarios} />;
}

function SimulationPlayer({ request, initialReport = null, scenarios = null, analysisRunId = null }) {
  const [savedOptions, setSavedOptions] = useState([]);
  const [savedReady, setSavedReady] = useState(!analysisRunId);
  const options = useMemo(
    () => scenarios || [{ id: request?.request_id || 'current', label: 'Паллетная перевозка', request, report: initialReport },
      ...savedOptions.filter((item) => item.id !== request?.request_id)],
    [scenarios, request, initialReport, savedOptions],
  );
  const [selected, setSelected] = useState(options[0]?.id || '');
  const active = useMemo(() => options.find((item) => item.id === selected) || options[0], [options, selected]);
  const [report, setReport] = useState(active?.report || null);
  const [viewMode, setViewMode] = useState('2D');
  const [runState, setRunState] = useState(null);
  const [error, setError] = useState('');
  const api = useRef(new SimulationApiSession());
  const bindingKey = report && active?.request
    ? `${active.request.scenario_spec.revision_id}:${report.replay.report_content_digest}`
    : `pending:${active?.request?.scenario_spec?.revision_id || 'none'}`;
  const [timeline, dispatch] = useReducer(reduceTimeline, bindingKey, createTimelineState);
  const [zoneChoice, setZoneChoice] = useState({ bindingKey: null, id: null });
  const persistedZoneId = useMemo(() => {
    try { return window.sessionStorage.getItem(`simulation-zone:${bindingKey}`); }
    catch { return null; }
  }, [bindingKey]);
  const selectedZoneId = zoneChoice.bindingKey === bindingKey ? zoneChoice.id : persistedZoneId;
  const previousFrame = useRef(null);
  const canvas = useRef(null);
  const startedRequest = useRef(null);

  const startRun = useCallback(async () => {
    if (!active?.request || startedRequest.current === active.request.request_id) return;
    startedRequest.current = active.request.request_id;
    setError('');
    setRunState({ state: 'PENDING', progress: { processed_events: 0, total_events: 0 } });
    const session = api.current;
    let generation;
    try {
      const pending = session.start(active.request, (state) => setRunState(state), analysisRunId);
      generation = session.generation;
      const terminal = await pending;
      if (generation !== session.generation) return;
      if (terminal?.state === 'SUCCEEDED') setReport(terminal.report);
      else if (terminal?.error) { setError(terminal.error.message); startedRequest.current = null; }
    } catch (failure) {
      if (generation !== session.generation) return;
      setError(failure.message);
      startedRequest.current = null;
    }
  }, [active, analysisRunId]);

  useEffect(() => {
    dispatch({ type: 'LOAD', bindingKey });
  }, [bindingKey]);

  useEffect(() => {
    if (report && active?.request) dispatch({ type: 'START' });
  }, [bindingKey, report, active?.request]);

  useEffect(() => {
    if (timeline.status !== 'RUNNING') return undefined;
    let animation;
    const tick = (stamp) => {
      if (previousFrame.current !== null) dispatch({ type: 'TICK', deltaMs: stamp - previousFrame.current });
      previousFrame.current = stamp;
      animation = requestAnimationFrame(tick);
    };
    animation = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(animation);
      previousFrame.current = null;
    };
  }, [timeline.status]);

  useEffect(() => () => api.current.invalidate(), []);

  useEffect(() => {
    if (!analysisRunId || !request) return undefined;
    const controller = new AbortController();
    fetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/simulations/projects/${encodeURIComponent(request.project_id)}/analysis-runs/${encodeURIComponent(analysisRunId)}/evidence`, {
      credentials: 'include', signal: controller.signal,
    }).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Не удалось открыть сохранённые симуляции: HTTP ${response.status}`)))
      .then((payload) => {
        const items = (payload.items || []).filter((item) => item.request?.scenario_spec?.revision_id === request.scenario_spec.revision_id)
          .map((item) => ({ id: item.request.request_id, label: item.request.process_chain?.stages?.length
            ? `Цепочка · ${item.request.process_chain.stages.map((stage) => stage.stage).join(', ')}` : 'Паллетная перевозка',
          request: item.request, report: item.report }));
        setSavedOptions(items);
        if (items.length) { const latest = items.at(-1); setSelected(latest.id); setReport(latest.report); }
        setSavedReady(true);
      })
      .catch((reason) => { if (reason.name !== 'AbortError') { setError(reason.message); setSavedReady(true); } });
    return () => controller.abort();
  }, [analysisRunId, request]);

  useEffect(() => {
    if (!analysisRunId || !savedReady || !active?.request || active.report
        || report?.request_id === active.request.request_id) return undefined;
    let current = true;
    api.current.loadSaved(active.request, analysisRunId)
      .then((state) => {
        if (!current) return;
        if (state?.state === 'SUCCEEDED') setReport(state.report);
        else if (state?.state === 'PENDING' || state?.state === 'RUNNING') startRun();
        else startRun();
      })
      .catch((reason) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [analysisRunId, savedReady, active, report?.request_id, startRun]);

  useEffect(() => {
    if (!analysisRunId && active?.request && !report) startRun();
  }, [analysisRunId, active, report, startRun]);

  const presentation = useMemo(() => {
    if (!active?.request || !report) return null;
    try {
      const bundle = parseSimulationBundle(active.request, report);
      const scene = buildSimulationScene(bundle.spec);
      return { bundle, scene, frame: frameAt(scene, bundle, timeline.simulationTimeUs) };
    } catch (failure) { return { failure }; }
  }, [active, report, timeline.simulationTimeUs]);

  const cancelRun = async () => {
    try {
      const state = await api.current.cancel();
      if (state) setRunState(state);
      startedRequest.current = null;
    } catch (failure) {
      setError(failure.message);
    }
  };

  const selectScenario = (id) => {
    const next = options.find((item) => item.id === id);
    api.current.invalidate();
    setSelected(id);
    setReport(next?.report || null);
    setRunState(null);
    setError('');
    startedRequest.current = null;
  };

  const startExtended = (extended) => {
    api.current.invalidate();
    setSavedOptions((current) => [...current.filter((item) => item.id !== extended.request_id), {
      id: extended.request_id, label: `Цепочка · ${extended.process_chain.stages.map((stage) => stage.stage).join(', ')}`,
      request: extended, report: null,
    }]);
    setSelected(extended.request_id);
    setReport(null); setRunState(null); setError(''); startedRequest.current = null;
  };

  const progress = runState?.progress;
  const progressValue = progress?.total_events ? Math.round(progress.processed_events / progress.total_events * 100) : 0;
  const warehouseScene = presentation?.scene?.kind === 'WAREHOUSE_TRANSPORT' ? presentation.scene : null;
  const activeZoneId = warehouseScene?.zones.some((zone) => zone.id === selectedZoneId)
    ? selectedZoneId : warehouseScene?.zones[0]?.id;
  const selectZone = (id) => {
    setZoneChoice({ bindingKey, id });
    try { window.sessionStorage.setItem(`simulation-zone:${bindingKey}`, id); } catch { /* private mode */ }
  };
  const saveSvg = () => {
    try {
      const metadata = visualExportMetadata(active.request, report, analysisRunId, presentation.frame.simulationTimeUs, activeZoneId, new Date().toISOString());
      downloadSimulationSvg(canvas.current?.querySelector('svg'), metadata, active.label);
    } catch (failure) { setError(failure.message); }
  };

  return (
    <section className="simulation-2d panel" id="visualization" aria-label="2D/3D-симуляция и отчёт">
      <header className="simulation-2d-header">
        <div>
          <p className="eyebrow">Симуляция процесса · схема работы</p>
          <h2>Схема работы и расчёт очереди</h2>
          <p>Координаты и движение роботов условные. Это схема процесса, не план объекта, телеметрия или инженерная сертификация.</p>
        </div>
        {options.length > 1 && (
          <label>Сценарий<select value={selected} onChange={(event) => selectScenario(event.target.value)}>{options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        )}
        {warehouseScene?.zones.length > 1 && <label>Зона склада
          <select value={activeZoneId} onChange={(event) => selectZone(event.target.value)}>
            {warehouseScene.zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.label}</option>)}
          </select>
        </label>}
      </header>

      {analysisRunId && request?.schema_version === 'simulation-request-v2'
        && <SimulationChainSetup baseRequest={request} onStart={startExtended} />}

      {!report && (
        <div className="simulation-run-box">
          <p>Запустите симуляцию процесса. Показатели будут получены из сохранённого серверного отчёта.</p>
          <button type="button" className="primary-action" onClick={startRun} disabled={['PENDING', 'RUNNING'].includes(runState?.state)}>Запустить расчёт симуляции</button>
          {['PENDING', 'RUNNING'].includes(runState?.state) && <button type="button" onClick={cancelRun}>Отменить</button>}
          {runState && <div aria-live="polite">{statusLabel(runState.state)} · {progressValue}% · {progress?.processed_events || 0}/{progress?.total_events || 0} событий</div>}
        </div>
      )}
      {(error || presentation?.failure) && <div className="simulation-error" role="alert">{error || presentation.failure.message}</div>}

      {presentation && !presentation.failure && (
        <>
          <div className="simulation-bindings">
            <strong>Исходный расчёт парка C11: {presentation.bundle.spec.analysis.capacity_run_id}</strong>
            <span>Физический сценарий: {active.label} · расчёт {analysisRunId || 'демо'}</span>
            {physicalInputs(presentation.bundle.spec).map((line, index) => <span key={index}>{line}</span>)}
            <p>Покупка и аренда используют общие сохранённые парк и график. Финансовые варианты и их ramp не переключают физический сценарий. CONSISTENT подтверждает согласованность модели; пригодность к внедрению требует обследования.</p>
            <span>Модельное время: {formatModelClock(report.model_start, presentation.frame.simulationTimeUs) || `${(presentation.frame.simulationTimeUs / 1_000_000).toFixed(1)} с`}</span>
            <button type="button" onClick={saveSvg}>Сохранить открытый 2D-кадр · SVG</button>
            {analysisRunId && <a href={`/api/v2/simulations/projects/${encodeURIComponent(active.request.project_id)}/analysis-runs/${encodeURIComponent(analysisRunId)}/${encodeURIComponent(active.request.request_id)}/evidence.json`} download>Скачать технические данные симуляции</a>}
            <details><summary>Технические подробности</summary>
              <span>Представление: {viewMode}</span>
              <span>scenario <code>{presentation.frame.scenarioRevisionId}</code></span>
              <span>report <code>{presentation.frame.reportId}</code></span>
              <span>Выполнено до конца окна <code>{report.queue.completed_by_measurement_end}</code></span>
              <span>Максимальная очередь <code>{report.queue.maximum_jobs}</code></span>
              <span>Предел парка <code>{report.capacity.expected_effective_per_hour} {report.capacity.unit}</code></span>
              <span>digest <code>{presentation.frame.reportDigest.slice(0, 18)}…</code></span>
              <span>seed <code>{presentation.frame.seed}</code></span>
            </details>
          </div>

          <div className="simulation-view-tabs" role="tablist" aria-label="Представление симуляции">
            {['2D', '3D'].map((mode) => <button key={mode} type="button" role="tab" aria-selected={viewMode === mode} onClick={() => setViewMode(mode)}>{mode}</button>)}
          </div>

          <div className="simulation-controls" aria-label="Управление timeline">
            <button type="button" onClick={() => dispatch({ type: 'START' })}>Старт</button>
            <button type="button" onClick={() => dispatch({ type: 'PAUSE' })}>Пауза</button>
            <button type="button" onClick={() => dispatch({ type: 'STOP' })}>Стоп</button>
            <button type="button" onClick={() => dispatch({ type: 'RESTART' })}>Перезапуск</button>
            <label>Скорость<select value={timeline.speed} onChange={(event) => dispatch({ type: 'SET_SPEED', speed: Number(event.target.value) })}>{[0.5, 1, 2, 4].map((speed) => <option key={speed} value={speed}>×{speed}</option>)}</select></label>
            <strong>{STATUS_LABELS[timeline.status]}</strong>
          </div>

          <div ref={canvas} role="tabpanel" hidden={viewMode !== '2D'}>{warehouseScene ? <Warehouse2DPlan scene={warehouseScene} frame={presentation.frame} selectedZoneId={activeZoneId} stages={report.stages} /> : <div className="simulation-canvas-wrap">
            <svg viewBox={`0 0 ${presentation.scene.width} ${presentation.scene.height}`} role="img" aria-label="Зоны, маршруты, парк и операции">
              <defs><marker id="simulation-flow-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" fill="#67e8f9" /></marker></defs>
              {presentation.scene.zones.map((zone) => <g key={zone.id}><rect className={`simulation-zone source-${zone.geometrySource.toLowerCase()}`} x={zone.x} y={zone.y} width={zone.width} height={zone.height} rx="16" /><text className="zone-name" x={zone.x + 16} y={zone.y + 26}>{zone.label}</text><text className="geometry-source" x={zone.x + 16} y={zone.y + 46}>{zone.geometryLabel}</text></g>)}
              {presentation.scene.routes.map((route) => <g key={route.id}><path className="simulation-route" d={path(route.points)} markerMid="url(#simulation-flow-arrow)" /><text className="geometry-source" x={route.points[0].x - 42} y={route.points[0].y - 20}>{route.originLabel}</text><text className="geometry-source" x={route.points[1].x - 42} y={route.points[1].y - 20}>{route.destinationLabel}</text><text className="geometry-source" x={route.points[0].x} y={route.points[0].y + 74}>{route.geometryLabel}{route.analyticalDistance ? ` · расчётный путь ${route.analyticalDistance.value} ${route.analyticalDistance.unit}` : ' · длина пути неизвестна'}</text></g>)}
              {presentation.scene.charging.map((marker) => <g key={marker.id} aria-label={marker.label}><text className="charging-badge" x={marker.x} y={marker.y} textAnchor="end">↯ учтено суммарно</text></g>)}
              {presentation.frame.robots.map((robot) => <g key={robot.id} transform={`translate(${robot.x} ${robot.y})`}><circle className="simulation-robot" r="9" /><text className="robot-label" x="12" y="4">{robot.ordinal + 1} · {robot.stage}</text></g>)}
            </svg>
            <div className="simulation-legend"><span>→ направление потока · обратный ход по нижней линии</span><span><i className="legend-robot" /> условное положение робота</span><span>↯ зарядка учтена агрегированно; точка не задана</span></div>
            <p className="simulation-schematic-note">Зоны и точки показаны схематично; предоставленная схема означает ссылку на геометрию, а не нанесённые здесь координаты. Операции и движение иллюстрируют процесс, показатели берутся из отчёта симуляции.</p>
          </div>}</div>
          <div role="tabpanel" hidden={viewMode !== '3D'}>{report.stages?.some((stage) => stage.status === 'MODELED') && <p className="simulation-schematic-note">3D показывает только паллетную перевозку. Для отбора, буфера и упаковки нет подтверждённой 3D-модели; их очереди и загрузка показаны в 2D и в отчёте выше.</p>}<RobCraftFrame key={bindingKey} scenarioSpec={active.request.scenario_spec} simulationReport={report} playback={timeline}
            selectedZoneId={warehouseScene ? activeZoneId : null} onZoneChange={warehouseScene ? selectZone : null} compact /></div>

          <div className="simulation-kpis">
            {metric('Парк', number(report.workload.fleet_units, ' роботов'))}
            {metric('Спрос', number(report.capacity.required_per_hour, ` ${report.capacity.unit}`))}
            {metric('Предел расчётного парка', number(report.capacity.expected_effective_per_hour, ` ${report.capacity.unit}`))}
            {metric('Выполнено до конца окна', number(report.capacity.observed_per_hour, ` ${report.capacity.unit}`), report.capacity.verdict)}
            {report.capacity.denominator === 'REQUIRED_DEMAND' && metric('Не выполнено к концу окна', number(report.capacity.demand_shortfall_per_hour, ` ${report.capacity.unit}`), `завершено после окна ${report.queue.completed_with_grace}/${report.queue.measurement_jobs} заданий`)}
            {report.capacity.denominator === 'REQUIRED_DEMAND' && metric('Запас до предела парка', number(report.capacity.capacity_headroom_per_hour, ` ${report.capacity.unit}`), statusLabel(report.capacity.ceiling_verdict))}
            {metric('Максимальная очередь', number(report.queue.maximum_jobs, ' заданий'), `среднее ожидание ${number(report.queue.mean_wait_seconds, ' с')}`)}
            {metric('Ожидание 95 % заданий', number(report.queue.p95_wait_seconds, ' с'), `полный цикл ${number(report.queue.p95_turnaround_seconds, ' с')}`)}
            {metric('Занятость парка', number(report.utilization.busy_fraction === null ? null : Number(report.utilization.busy_fraction) * 100, '%'), `полезная работа ${number(report.utilization.productive_fraction === null ? null : Number(report.utilization.productive_fraction) * 100, '%')}`)}
          </div>

          {report.stages && <div className="simulation-kpis" aria-label="Стадии складской цепочки">{report.stages.map((stage) =>
            metric(({ PICKING: 'Отбор', BUFFER: 'Буфер', FEED_TO_PACK: 'Подача к упаковке', PACKAGING: 'Упаковка' })[stage.stage],
              stage.status === 'MODELED' ? number(stage.maximum_queue_jobs, ' в очереди') : 'Внешняя граница',
              stage.status === 'MODELED' ? `Занятость ${number(Number(stage.utilization_fraction) * 100, '%')} · ${stage.resource_kind} · ${stage.resource_id}` : 'Нет отдельной скорости, ресурса или подтверждённой связи', stage.stage)
          )}</div>}

          {hasCapacityWarning(report) && (
            <div className="simulation-warning" role="status">{report.capacity.verdict === 'DEVIATION' ? (report.capacity.denominator === 'REQUIRED_DEMAND' ? 'К концу окна выполнено более чем на 10% меньше заданного спроса.' : 'Исторический отчёт: расхождение с максимумом парка превышает 10%.') : report.capacity.verdict === 'OVERLOADED' ? 'Спрос превышает возможности парка; очередь не закрыта к концу окна.' : 'Наблюдаемый поток несовместим с входными данными.'} Отклонение: {number(report.capacity.deviation_percent, '%')}.</div>
          )}
          <div className={`simulation-sla sla-${report.sla.verdict.toLowerCase()}`}>{SLA_LABELS[report.sla.verdict]}{report.sla.on_time_fraction !== null && ` · вовремя ${number(Number(report.sla.on_time_fraction) * 100, '%')}`}</div>
          <div className="simulation-notes">
                <div><h3>Ограничения отчёта</h3><ul>{report.limitations.map((item) => <li key={item}>{humanizePresentation(item)}</li>)}</ul></div>
                <div><h3>Геометрия и экономика</h3><p>{presentation.bundle.spec.finance === null ? 'Финансовый расчёт не предоставлен; схема процесса доступна.' : 'Финансовый расчёт связан с симуляцией; браузер не считает деньги.'}</p><p>Условные координаты используются только для показа и не меняют расчётную длину маршрута.</p></div>
          </div>
        </>
      )}
    </section>
  );
}
