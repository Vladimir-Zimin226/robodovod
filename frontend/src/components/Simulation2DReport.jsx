import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
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

const STATUS_LABELS = {
  STOPPED: 'Остановлено', RUNNING: 'Воспроизведение', PAUSED: 'Пауза',
};
const SLA_LABELS = {
  PASS: 'PASS по заданному SLA',
  FAIL: 'FAIL по заданному SLA',
  CONDITIONAL: 'CONDITIONAL · модель неполна',
  NOT_EVALUATED: 'NOT_EVALUATED · SLA не оценён',
};

function number(value, suffix = '') {
  if (value === null || value === undefined) return 'N/A';
  const parsed = Number(value);
  return `${Number.isFinite(parsed) ? new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(parsed) : value}${suffix}`;
}

function metric(label, value, detail) {
  return <div className="simulation-kpi"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

function path(points) {
  return points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
}

export default function Simulation2DReport({ request, initialReport = null, scenarios = null, analysisRunId = null }) {
  const options = useMemo(
    () => scenarios || [{ id: request?.request_id || 'current', label: 'Текущий сценарий', request, report: initialReport }],
    [scenarios, request, initialReport],
  );
  const [selected, setSelected] = useState(options[0]?.id || '');
  const active = useMemo(() => options.find((item) => item.id === selected) || options[0], [options, selected]);
  const [report, setReport] = useState(active?.report || null);
  const [runState, setRunState] = useState(null);
  const [error, setError] = useState('');
  const api = useRef(new SimulationApiSession());
  const bindingKey = report && active?.request
    ? `${active.request.scenario_spec.revision_id}:${report.replay.report_content_digest}`
    : `pending:${active?.request?.scenario_spec?.revision_id || 'none'}`;
  const [timeline, dispatch] = useReducer(reduceTimeline, bindingKey, createTimelineState);
  const previousFrame = useRef(null);

  useEffect(() => {
    dispatch({ type: 'LOAD', bindingKey });
  }, [bindingKey]);

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
    if (!analysisRunId || !active?.request || active.report) return undefined;
    let current = true;
    api.current.loadSaved(active.request, analysisRunId)
      .then((state) => { if (current && state?.state === 'SUCCEEDED') setReport(state.report); })
      .catch((reason) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [analysisRunId, active]);

  const presentation = useMemo(() => {
    if (!active?.request || !report) return null;
    try {
      const bundle = parseSimulationBundle(active.request, report);
      const scene = buildSimulationScene(bundle.spec);
      return { bundle, scene, frame: frameAt(scene, bundle, timeline.simulationTimeUs) };
    } catch (failure) { return { failure }; }
  }, [active, report, timeline.simulationTimeUs]);

  const startRun = async () => {
    if (!active?.request) return;
    setError('');
    setRunState({ state: 'PENDING', progress: { processed_events: 0, total_events: 0 } });
    try {
      const terminal = await api.current.start(active.request, (state) => setRunState(state), analysisRunId);
      if (terminal?.state === 'SUCCEEDED') setReport(terminal.report);
      else if (terminal?.error) setError(terminal.error.message);
    } catch (failure) {
      setError(failure.message);
    }
  };

  const cancelRun = async () => {
    try {
      const state = await api.current.cancel();
      if (state) setRunState(state);
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
  };

  const progress = runState?.progress;
  const progressValue = progress?.total_events ? Math.round(progress.processed_events / progress.total_events * 100) : 0;

  return (
    <section className="simulation-2d panel" id="visualization" aria-label="2D-симуляция и отчёт">
      <header className="simulation-2d-header">
        <div>
          <p className="eyebrow">C23 {report?.schema_version || 'SimulationReport'} · схема процесса</p>
          <h2>Схема работы и расчёт очереди</h2>
          <p>Координаты и движение роботов условные. Это схема процесса, не план объекта, телеметрия или инженерная сертификация.</p>
        </div>
        {options.length > 1 && (
          <label>Сценарий<select value={selected} onChange={(event) => selectScenario(event.target.value)}>{options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        )}
      </header>

      {!report && (
        <div className="simulation-run-box">
          <p>Запустите детерминированный C23 scheduler. KPI будут получены только из backend-отчёта.</p>
          <button type="button" className="primary-action" onClick={startRun} disabled={['PENDING', 'RUNNING'].includes(runState?.state)}>Запустить расчёт симуляции</button>
          {['PENDING', 'RUNNING'].includes(runState?.state) && <button type="button" onClick={cancelRun}>Отменить</button>}
          {runState && <div aria-live="polite">{runState.state} · {progressValue}% · {progress?.processed_events || 0}/{progress?.total_events || 0} событий</div>}
        </div>
      )}
      {(error || presentation?.failure) && <div className="simulation-error" role="alert">{error || presentation.failure.message}</div>}

      {presentation && !presentation.failure && (
        <>
          <div className="simulation-bindings">
            <span>scenario <code>{presentation.frame.scenarioRevisionId}</code></span>
            <span>report <code>{presentation.frame.reportId}</code></span>
            <span>digest <code>{presentation.frame.reportDigest.slice(0, 18)}…</code></span>
            <span>seed <code>{presentation.frame.seed}</code></span>
            <span>t={(presentation.frame.simulationTimeUs / 1_000_000).toFixed(1)} s</span>
            {analysisRunId && <a href={`/api/v2/simulations/projects/${encodeURIComponent(active.request.project_id)}/analysis-runs/${encodeURIComponent(analysisRunId)}/${encodeURIComponent(active.request.request_id)}/evidence.json`} download>Скачать evidence C23 JSON</a>}
          </div>

          <div className="simulation-controls" aria-label="Управление timeline">
            <button type="button" onClick={() => dispatch({ type: 'START' })}>Старт</button>
            <button type="button" onClick={() => dispatch({ type: 'PAUSE' })}>Пауза</button>
            <button type="button" onClick={() => dispatch({ type: 'STOP' })}>Стоп</button>
            <button type="button" onClick={() => dispatch({ type: 'RESTART' })}>Перезапуск</button>
            <label>Скорость<select value={timeline.speed} onChange={(event) => dispatch({ type: 'SET_SPEED', speed: Number(event.target.value) })}>{[0.5, 1, 2, 4].map((speed) => <option key={speed} value={speed}>×{speed}</option>)}</select></label>
            <strong>{STATUS_LABELS[timeline.status]}</strong>
          </div>

          <div className="simulation-canvas-wrap">
            <svg viewBox={`0 0 ${presentation.scene.width} ${presentation.scene.height}`} role="img" aria-label="Зоны, маршруты, парк и операции">
              <defs><marker id="simulation-flow-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" fill="#67e8f9" /></marker></defs>
              {presentation.scene.zones.map((zone) => <g key={zone.id}><rect className={`simulation-zone source-${zone.geometrySource.toLowerCase()}`} x={zone.x} y={zone.y} width={zone.width} height={zone.height} rx="16" /><text className="zone-name" x={zone.x + 16} y={zone.y + 26}>{zone.label}</text><text className="geometry-source" x={zone.x + 16} y={zone.y + 46}>{zone.geometryLabel}</text></g>)}
              {presentation.scene.routes.map((route) => <g key={route.id}><path className="simulation-route" d={path(route.points)} markerMid="url(#simulation-flow-arrow)" /><text className="geometry-source" x={route.points[0].x - 42} y={route.points[0].y - 20}>{route.originLabel}</text><text className="geometry-source" x={route.points[1].x - 42} y={route.points[1].y - 20}>{route.destinationLabel}</text><text className="geometry-source" x={route.points[0].x} y={route.points[0].y + 74}>{route.geometryLabel}{route.analyticalDistance ? ` · расчётный путь ${route.analyticalDistance.value} ${route.analyticalDistance.unit}` : ' · длина пути неизвестна'}</text></g>)}
              {presentation.scene.charging.map((marker) => <g key={marker.id} aria-label={marker.label}><text className="charging-badge" x={marker.x} y={marker.y} textAnchor="end">↯ aggregate only</text></g>)}
              {presentation.frame.robots.map((robot) => <g key={robot.id} transform={`translate(${robot.x} ${robot.y})`}><circle className="simulation-robot" r="9" /><text className="robot-label" x="12" y="4">{robot.ordinal + 1} · {robot.stage}</text></g>)}
            </svg>
            <div className="simulation-legend"><span>→ направление потока · обратный ход по нижней линии</span><span><i className="legend-robot" /> условное положение робота</span><span>↯ зарядка учтена агрегированно; точка не задана</span></div>
            <p className="simulation-schematic-note">Зоны и точки показаны схематично; даже PROVIDED означает ссылку на геометрию, а не нанесённые здесь координаты. Операции и движение иллюстрируют процесс, KPI берутся из отчёта C23.</p>
          </div>

          <div className="simulation-kpis">
            {metric('Парк', number(report.workload.fleet_units, ' роботов'))}
            {metric('Спрос', number(report.capacity.required_per_hour, ` ${report.capacity.unit}`))}
            {metric('Предел парка C11', number(report.capacity.expected_effective_per_hour, ` ${report.capacity.unit}`))}
            {metric('Выполнено до конца окна', number(report.capacity.observed_per_hour, ` ${report.capacity.unit}`), report.capacity.verdict)}
            {report.capacity.denominator === 'REQUIRED_DEMAND' && metric('Не выполнено к концу окна', number(report.capacity.demand_shortfall_per_hour, ` ${report.capacity.unit}`), `завершено с grace ${report.queue.completed_with_grace}/${report.queue.measurement_jobs} заданий`)}
            {report.capacity.denominator === 'REQUIRED_DEMAND' && metric('Запас до предела парка', number(report.capacity.capacity_headroom_per_hour, ` ${report.capacity.unit}`), report.capacity.ceiling_verdict)}
            {metric('Очередь max', number(report.queue.maximum_jobs, ' jobs'), `mean wait ${number(report.queue.mean_wait_seconds, ' s')}`)}
            {metric('P95 ожидание', number(report.queue.p95_wait_seconds, ' s'), `turnaround ${number(report.queue.p95_turnaround_seconds, ' s')}`)}
            {metric('Загрузка busy', number(report.utilization.busy_fraction === null ? null : Number(report.utilization.busy_fraction) * 100, '%'), `productive ${number(report.utilization.productive_fraction === null ? null : Number(report.utilization.productive_fraction) * 100, '%')}`)}
          </div>

          {hasCapacityWarning(report) && (
            <div className="simulation-warning" role="status">{report.capacity.verdict === 'DEVIATION' ? (report.capacity.denominator === 'REQUIRED_DEMAND' ? 'К концу окна выполнено более чем на 10% меньше заданного спроса.' : 'Исторический отчёт: расхождение с максимумом парка превышает 10%.') : report.capacity.verdict === 'OVERLOADED' ? 'Спрос превышает возможности парка; очередь не закрыта к концу окна.' : 'Наблюдаемый поток несовместим с входными данными.'} Отклонение: {number(report.capacity.deviation_percent, '%')} · denominator {report.capacity.denominator}.</div>
          )}
          <div className={`simulation-sla sla-${report.sla.verdict.toLowerCase()}`}>{SLA_LABELS[report.sla.verdict]}{report.sla.on_time_fraction !== null && ` · on-time ${number(Number(report.sla.on_time_fraction) * 100, '%')}`}</div>
          <div className="simulation-notes">
            <div><h3>Ограничения отчёта</h3><ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><h3>Геометрия и экономика</h3><p>{presentation.bundle.spec.finance === null ? 'Capacity-only: финансовый snapshot не предоставлен; визуализация полностью доступна.' : 'Finance binding показан только как immutable reference; браузер не считает деньги.'}</p><p>Synthetic coordinates используются только для показа и не переписывают analytical route/distance.</p></div>
          </div>
          <RobCraftFrame scenarioSpec={active.request.scenario_spec} simulationReport={report} compact />
        </>
      )}
    </section>
  );
}
