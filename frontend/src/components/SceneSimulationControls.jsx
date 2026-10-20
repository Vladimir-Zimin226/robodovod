import { useEffect, useRef, useState } from 'react';
import { sceneForKind } from '../sceneModel.js';
import { playbackDuration, playbackPose } from '../simulationPlayback.js';
import { simulationOptions } from '../simulationRouteOptions.js';

const API = import.meta.env.VITE_API_URL || '';
const DEMO_DEFAULTS = { speedLoaded: '0.8', speedEmpty: '1', pickupService: '25',
  dropoffService: '20', turnDelay: '8', unitsPerCycle: '1' };
const STATUS_TEXT = { MODELED: 'Маршрут рассчитан', CAPACITY_SHORTFALL: 'Нагрузка выше мощности сценария',
  NEEDS_INPUT: 'Нужно уточнить параметры', NO_ROUTE: 'Проезд между зонами невозможен' };
const FIELD_TEXT = { speed_loaded_mps: 'скорость с грузом', speed_empty_mps: 'скорость без груза',
  pickup_service_s: 'время погрузки', dropoff_service_s: 'время разгрузки',
  turn_delay_s: 'задержку на поворотах', units_per_cycle: 'единиц за рейс',
  demand_units_per_hour: 'спрос в час', robot_availability: 'доступность робота' };

function NumericField({ label, value, onChange, min = '0', step = 'any' }) {
  return <label className="scene-sim-field"><span>{label}</span><input type="number" min={min} step={step}
    value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

export default function SceneSimulationControls({ kind, roleInput, report, onSimulated, onScenario, onChanged, onPlayback }) {
  const scene = sceneForKind(kind);
  const options = simulationOptions(roleInput, report);
  const [selection, setSelection] = useState(options[0]?.key || '');
  const [values, setValues] = useState({ ...DEMO_DEFAULTS, arrivalBurst: '1', pickupX: '', pickupY: '',
    dropoffX: '', dropoffY: '', obstacleX: '', obstacleY: '', obstacleWidth: '', obstacleHeight: '',
    laneX: '', laneY: '', laneWidth: '', laneHeight: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);
  const [changed, setChanged] = useState(false);
  const editRevision = useRef(0);
  const mounted = useRef(true);
  const request = useRef(null);
  const playback = useRef({ samples: [], elapsed: 0, lastFrame: null });
  const [playState, setPlayState] = useState('READY');
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; request.current?.abort(); }; }, []);
  useEffect(() => {
    if (playState !== 'RUNNING') return undefined;
    let frame;
    const tick = (now) => {
      const state = playback.current;
      if (state.lastFrame !== null) state.elapsed = Math.min(playbackDuration(state.samples),
        state.elapsed + Math.min((now - state.lastFrame) / 1000, 0.1));
      state.lastFrame = now;
      setElapsed(state.elapsed);
      onPlayback(playbackPose(state.samples, state.elapsed));
      if (state.elapsed >= playbackDuration(state.samples)) { setPlayState('FINISHED'); return; }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); playback.current.lastFrame = null; };
  }, [playState, onPlayback]);
  const selected = options.find((item) => item.key === selection) || options[0];
  const invalidate = () => { editRevision.current += 1; request.current?.abort();
    playback.current = { samples: [], elapsed: 0, lastFrame: null };
    setPlayState('READY'); setElapsed(0); setDuration(0); onPlayback(null); setChanged(true); setSummary(null); onChanged(); };
  const patch = (key, value) => { invalidate(); setValues((current) => ({ ...current, [key]: value })); };
  if (!scene || !options.length) return <p>В выбранных работах маршрут между зонами пока не моделируется. Выберите перевозку багажа, материалов клиники или груза склада.</p>;
  const zones = Object.fromEntries(scene.zones.map((zone) => [zone.zone_id, zone]));
  const coordinate = (x, y, fallback) => [x === '' ? fallback[0] : Number(x), y === '' ? fallback[1] : Number(y)];
  const optional = (key) => values[key] === '' ? null : Number(values[key]);
  const submit = async (event) => {
    event.preventDefault();
    const submittedRevision = editRevision.current;
    request.current?.abort();
    request.current = new AbortController();
    playback.current = { samples: [], elapsed: 0, lastFrame: null };
    setPlayState('READY'); setElapsed(0); setDuration(0); onPlayback(null); onChanged();
    setBusy(true); setError(''); setSummary(null);
    try {
      const next = structuredClone(roleInput);
      const withObstacle = [values.obstacleX, values.obstacleY, values.obstacleWidth, values.obstacleHeight].some((value) => value !== '');
      if (withObstacle && [values.obstacleX, values.obstacleY, values.obstacleWidth, values.obstacleHeight].some((value) => value === '')) {
        throw new Error('Для препятствия заполните X, Y, ширину и длину.');
      }
      const laneFields = [values.laneX, values.laneY, values.laneWidth, values.laneHeight];
      const withLane = laneFields.some((value) => value !== '');
      if (withLane && laneFields.some((value) => value === '')) {
        throw new Error('Для узкого участка заполните X, Y, ширину и длину.');
      }
      const simulation = { scene_revision: scene.revision,
        pickup_xy_m: coordinate(values.pickupX, values.pickupY, zones.pickup.center_xy_m),
        dropoff_xy_m: coordinate(values.dropoffX, values.dropoffY, zones.delivery.center_xy_m),
        speed_loaded_mps: optional('speedLoaded'), speed_empty_mps: optional('speedEmpty'),
        pickup_service_s: optional('pickupService'), dropoff_service_s: optional('dropoffService'),
        turn_delay_s: optional('turnDelay'), units_per_cycle: optional('unitsPerCycle'),
        arrival_burst_size: Number(values.arrivalBurst),
        shared_lane: withLane ? { x: Number(values.laneX), y: Number(values.laneY),
          width: Number(values.laneWidth), height: Number(values.laneHeight) } : null,
        extra_obstacles: withObstacle ? [{ x: Number(values.obstacleX), y: Number(values.obstacleY),
          width: Number(values.obstacleWidth), height: Number(values.obstacleHeight) }] : [] };
      if (report.kind) next.roles[selected.roleIndex].works[selected.workIndex].simulation = simulation;
      else next.roles[selected.roleIndex].simulation = simulation;
      const scenarioOnly = report.kind
        ? ['SCENARIO_TYPE', ''].includes(next.roles[selected.roleIndex].works[selected.workIndex].selected_position_id || '')
        : !report.roles[selected.roleIndex]?.selected_position_id;
      if (scenarioOnly) {
        const routePath = report.kind ? `/api/v2/object-roles/${report.kind}/route-preview`
          : '/api/v2/warehouse-roles/route-preview';
        const routeResponse = await fetch(`${API}${routePath}`, {
          method: 'POST', credentials: 'include', signal: request.current.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ input: next, role_index: selected.roleIndex,
            ...(report.kind ? { work_index: selected.workIndex } : {}) }),
        });
        if (!routeResponse.ok) {
          const body = await routeResponse.json().catch(() => ({}));
          throw new Error(typeof body.detail === 'string' ? body.detail : `Ошибка маршрута: ${routeResponse.status}`);
        }
        const route = await routeResponse.json();
        if (!mounted.current || submittedRevision !== editRevision.current) return;
        const result = route.simulation;
        onScenario({ request: simulation, result });
        setSummary({ simulation: result, fleet: null, npv: null, scenarioOnly: true,
          sampledDemand: route.simulated_demand_units_per_hour,
          requestedDemand: route.requested_demand_units_per_hour });
        setChanged(false);
        const samples = result.timestep_pose_samples || [];
        if (samples.length > 1 && ['MODELED', 'CAPACITY_SHORTFALL'].includes(result.status)) {
          playback.current = { samples, elapsed: 0, lastFrame: null };
          setElapsed(0); setDuration(playbackDuration(samples)); onPlayback(playbackPose(samples, 0)); setPlayState('RUNNING');
        }
        return;
      }
      const path = report.kind ? `/api/v2/object-roles/${report.kind}/preview` : '/api/v2/warehouse-roles/preview';
      const response = await fetch(`${API}${path}`, { method: 'POST', credentials: 'include', signal: request.current.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(next) });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : `Ошибка пересчёта: ${response.status}`);
      }
      const result = await response.json();
      if (!mounted.current || submittedRevision !== editRevision.current) return;
      const selectedRole = result.roles[selected.roleIndex];
      const row = report.kind ? selectedRole?.works?.[selected.workIndex]
        : selectedRole?.candidates?.find((item) => item.position_id === selectedRole.selected_position_id);
      if (!row?.simulation) throw new Error(selectedRole?.selected_position_id
        ? 'Симуляция не найдена в ответе сервера. Проверьте пригодность выбранной модели.'
        : 'Для этой работы каталог не подобрал робота. Маршрут и экономику подтвердить нельзя; выберите другую работу или модель.');
      onSimulated(result, next, { request: simulation, result: row.simulation });
      const modeledFleet = row.simulation.fleet_required;
      setSummary({ simulation: row.simulation, fleet: row.fleet,
        npv: modeledFleet == null ? null : report.kind ? row.purchase?.npv_rub : row.npv_rub });
      setChanged(false);
      const samples = row.simulation.timestep_pose_samples || [];
      if (samples.length > 1 && ['MODELED', 'CAPACITY_SHORTFALL'].includes(row.simulation.status)) {
        playback.current = { samples, elapsed: 0, lastFrame: null };
        setElapsed(0); setDuration(playbackDuration(samples)); onPlayback(playbackPose(samples, 0)); setPlayState('RUNNING');
      } else { setPlayState('READY'); onPlayback(null); }
    } catch (failure) { if (mounted.current && submittedRevision === editRevision.current && failure.name !== 'AbortError') setError(failure.message); }
    finally { if (mounted.current && submittedRevision === editRevision.current) setBusy(false); }
  };
  return <section className="scene-sim-controls" aria-label="Расчёт маршрута">
    <h2>Запустить симуляцию маршрута</h2>
    <p>Сценарные допущения: с грузом 0,8 м/с, без груза 1 м/с, погрузка 25 с, разгрузка 20 с, повороты 8 с, 1 единица за рейс. Их можно изменить ниже. Спрос и доступность берутся из шага «Работа». Зарядка не моделируется.</p>
    <form onSubmit={submit}>
      <label className="scene-sim-field"><span>Работа</span><select value={selected.key}
        onChange={(event) => { invalidate(); setSelection(event.target.value); }}>
        {options.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
      <details><summary>Изменить сценарные параметры</summary><div className="scene-sim-fields">
        <NumericField label="Скорость с грузом, м/с" value={values.speedLoaded} onChange={(v) => patch('speedLoaded', v)} min="0.01" />
        <NumericField label="Скорость без груза, м/с" value={values.speedEmpty} onChange={(v) => patch('speedEmpty', v)} min="0.01" />
        <NumericField label="Единиц за рейс" value={values.unitsPerCycle} onChange={(v) => patch('unitsPerCycle', v)} min="0.01" />
        <NumericField label="Погрузка, с" value={values.pickupService} onChange={(v) => patch('pickupService', v)} />
        <NumericField label="Разгрузка, с" value={values.dropoffService} onChange={(v) => patch('dropoffService', v)} />
        <NumericField label="Задержка на поворотах, с" value={values.turnDelay} onChange={(v) => patch('turnDelay', v)} />
        <NumericField label="Заявок одновременно (1 = ровный поток)" value={values.arrivalBurst} onChange={(v) => patch('arrivalBurst', v)} min="1" step="1" />
      </div></details>
      <details><summary>Изменить точки и добавить препятствие</summary>
        <div className="scene-sim-fields">
          <NumericField label={`Отбор X, м (обычно ${zones.pickup.center_xy_m[0]})`} value={values.pickupX} onChange={(v) => patch('pickupX', v)} />
          <NumericField label={`Отбор Y, м (обычно ${zones.pickup.center_xy_m[1]})`} value={values.pickupY} onChange={(v) => patch('pickupY', v)} />
          <NumericField label={`Доставка X, м (обычно ${zones.delivery.center_xy_m[0]})`} value={values.dropoffX} onChange={(v) => patch('dropoffX', v)} />
          <NumericField label={`Доставка Y, м (обычно ${zones.delivery.center_xy_m[1]})`} value={values.dropoffY} onChange={(v) => patch('dropoffY', v)} />
          <NumericField label="Препятствие: центр X, м" value={values.obstacleX} onChange={(v) => patch('obstacleX', v)} />
          <NumericField label="Препятствие: центр Y, м" value={values.obstacleY} onChange={(v) => patch('obstacleY', v)} />
          <NumericField label="Препятствие: ширина, м" value={values.obstacleWidth} onChange={(v) => patch('obstacleWidth', v)} />
          <NumericField label="Препятствие: длина, м" value={values.obstacleHeight} onChange={(v) => patch('obstacleHeight', v)} />
        </div></details>
      <details><summary>Добавить общий узкий участок (один робот одновременно)</summary>
        <p>Прямоугольник должен пересекать маршрут с грузом и обратный маршрут один раз. Координаты задаются в метрах той же сцены.</p>
        <div className="scene-sim-fields">
          <NumericField label="Участок: центр X, м" value={values.laneX} onChange={(v) => patch('laneX', v)} />
          <NumericField label="Участок: центр Y, м" value={values.laneY} onChange={(v) => patch('laneY', v)} />
          <NumericField label="Участок: ширина, м" value={values.laneWidth} onChange={(v) => patch('laneWidth', v)} min="0.01" />
          <NumericField label="Участок: длина, м" value={values.laneHeight} onChange={(v) => patch('laneHeight', v)} min="0.01" />
        </div></details>
      <button type="submit" className="primary-action" disabled={busy}>{busy ? 'Считаю…' : 'Запустить симуляцию'}</button>
    </form>
    {duration > 0 && <div className="scene-playback-controls" role="group" aria-label="Управление движением">
      <button type="button" onClick={() => setPlayState(playState === 'RUNNING' ? 'PAUSED' : 'RUNNING')}>
        {playState === 'RUNNING' ? 'Пауза' : 'Продолжить'}</button>
      <button type="button" onClick={() => { playback.current.elapsed = 0; playback.current.lastFrame = null;
        setElapsed(0); onPlayback(playbackPose(playback.current.samples, 0)); setPlayState('RUNNING'); }}>Сначала</button>
      <span role="status">{Math.floor(elapsed)} / {Math.ceil(duration)} с · {playState === 'RUNNING' ? 'Движется' : playState === 'PAUSED' ? 'Пауза' : 'Завершено'}</span>
    </div>}
    {error && <p role="alert">{error}</p>}
    {summary && <div role="status"><p>Статус: <strong>{STATUS_TEXT[summary.simulation.status] || summary.simulation.status}</strong>{changed ? ' · ввод изменён, нужен повторный пересчёт' : ''}.</p>
      {summary.simulation.missing?.length > 0 && <p>Нужно указать: {summary.simulation.missing.map((field) => FIELD_TEXT[field] || field).join(', ')}.</p>}
      <p>Маршрут с грузом: {summary.simulation.distance_loaded_m ?? '—'} м; пустой ход: {summary.simulation.distance_empty_m ?? '—'} м; ожидание: {summary.simulation.time_wait_s ?? 'не рассчитано'} с; цикл: {summary.simulation.cycle_s ?? 'не рассчитан'} с.</p>
      {summary.simulation.shared_lane && <p>Узкий участок: среднее ожидание {summary.simulation.shared_lane.mean_wait_s} с; проездов {summary.simulation.shared_lane.events}; пропускная способность {summary.simulation.shared_lane.capacity_per_hour} рейсов/ч.</p>}
      <p>{summary.scenarioOnly ? 'Сценарная потребность' : 'Парк'}: {summary.simulation.fleet_required ?? 'не рассчитан'}; NPV покупки этой работы: {summary.npv == null ? 'не рассчитан' : `${Number(summary.npv).toLocaleString('ru-RU')} ₽`}.</p>
      {summary.scenarioOnly && <p role="alert">Это движение условного робота: каталог не подтвердил модель. Сценарный парк не является рекомендацией к закупке, денежный результат не пересчитан.</p>}
      {summary.sampledDemand < summary.requestedDemand && <p role="alert">Поток {summary.requestedDemand.toLocaleString('ru-RU')} ед./ч превышает предел серверного прогона. Для показа маршрута использован поток {summary.sampledDemand.toLocaleString('ru-RU')} ед./ч; парк и пропускная способность по исходному потоку не рассчитаны.</p>}
      <p>Пригодность робота, безопасность и зарядка требуют отдельной проверки.</p>
      <details><summary>Детали проверки</summary><p>Флаги расчёта: {summary.simulation.flags.join(', ')}.</p></details>
    </div>}
  </section>;
}
