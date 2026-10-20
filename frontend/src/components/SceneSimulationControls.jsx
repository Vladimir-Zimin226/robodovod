import { useEffect, useRef, useState } from 'react';
import { sceneForKind } from '../sceneModel.js';

const API = import.meta.env.VITE_API_URL || '';
const TRANSPORT_ROLES = new Set(['forklift_driver', 'loader', 'picker', 'storekeeper']);

function optionsFor(input, report) {
  if (!input || !report) return [];
  if (report.kind) return input.roles.flatMap((role, roleIndex) => role.works
    .map((work, workIndex) => ({ roleIndex, workIndex, key: `${roleIndex}:${workIndex}`,
      label: `${report.roles[roleIndex]?.label || role.role_code}: ${work.technical_task}`, unit: work.unit }))
    .filter((item) => item.unit !== 'm2'));
  return input.roles.map((role, roleIndex) => ({ roleIndex, key: `${roleIndex}`,
    label: report.roles[roleIndex]?.label || role.role_code }))
    .filter((item) => TRANSPORT_ROLES.has(input.roles[item.roleIndex].role_code)
      && report.roles[item.roleIndex]?.selected_position_id);
}

function NumericField({ label, value, onChange, min = '0', step = 'any' }) {
  return <label className="scene-sim-field"><span>{label}</span><input type="number" min={min} step={step}
    value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

export default function SceneSimulationControls({ kind, roleInput, report, onSimulated, onChanged }) {
  const scene = sceneForKind(kind);
  const options = optionsFor(roleInput, report);
  const [selection, setSelection] = useState(options[0]?.key || '');
  const [values, setValues] = useState({ speedLoaded: '', speedEmpty: '', pickupService: '',
    dropoffService: '', turnDelay: '', unitsPerCycle: '', arrivalBurst: '1', pickupX: '', pickupY: '',
    dropoffX: '', dropoffY: '', obstacleX: '', obstacleY: '', obstacleWidth: '', obstacleHeight: '',
    laneX: '', laneY: '', laneWidth: '', laneHeight: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);
  const [changed, setChanged] = useState(false);
  const editRevision = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const selected = options.find((item) => item.key === selection) || options[0];
  const patch = (key, value) => { editRevision.current += 1; setValues((current) => ({ ...current, [key]: value })); setChanged(true); setSummary(null); onChanged(); };
  if (!scene || !options.length) return <p>Для этой оценки пока нет транспортной работы с редактируемым маршрутом.</p>;
  const zones = Object.fromEntries(scene.zones.map((zone) => [zone.zone_id, zone]));
  const coordinate = (x, y, fallback) => [x === '' ? fallback[0] : Number(x), y === '' ? fallback[1] : Number(y)];
  const optional = (key) => values[key] === '' ? null : Number(values[key]);
  const submit = async (event) => {
    event.preventDefault();
    const submittedRevision = editRevision.current;
    setBusy(true); setError('');
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
      const path = report.kind ? `/api/v2/object-roles/${report.kind}/preview` : '/api/v2/warehouse-roles/preview';
      const response = await fetch(`${API}${path}`, { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(next) });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : `Ошибка пересчёта: ${response.status}`);
      }
      const result = await response.json();
      if (!mounted.current || submittedRevision !== editRevision.current) return;
      const row = report.kind ? result.roles[selected.roleIndex]?.works[selected.workIndex]
        : result.roles[selected.roleIndex]?.candidates.find((item) => item.position_id === result.roles[selected.roleIndex].selected_position_id);
      if (!row?.simulation) throw new Error('Симуляция не найдена в ответе сервера.');
      onSimulated(result, next, { request: simulation, result: row.simulation });
      setSummary({ simulation: row.simulation, fleet: row.fleet,
        npv: report.kind ? row.purchase?.npv_rub : row.npv_rub });
      setChanged(false);
    } catch (failure) { if (mounted.current && submittedRevision === editRevision.current) setError(failure.message); }
    finally { if (mounted.current) setBusy(false); }
  };
  return <section className="scene-sim-controls" aria-label="Расчёт маршрута">
    <h2>Рассчитать маршрут и обновить деньги</h2>
    <p>Выберите транспортную работу. Скорости и объём за рейс задаются вами как сценарные входы; спрос и доступность берутся из шага «Работа». Очередь считается у зон погрузки и разгрузки. Можно задать один узкий участок с одновременным проездом только одного робота; без него встречный поток не моделируется. Зарядка пока не моделируется. При отсутствии пути или данных эффект этой работы обнуляется.</p>
    <form onSubmit={submit}>
      <label className="scene-sim-field"><span>Работа</span><select value={selected.key}
        onChange={(event) => { editRevision.current += 1; setSelection(event.target.value); setChanged(true); setSummary(null); onChanged(); }}>
        {options.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
      <div className="scene-sim-fields">
        <NumericField label="Скорость с грузом, м/с" value={values.speedLoaded} onChange={(v) => patch('speedLoaded', v)} min="0.01" />
        <NumericField label="Скорость без груза, м/с" value={values.speedEmpty} onChange={(v) => patch('speedEmpty', v)} min="0.01" />
        <NumericField label="Единиц за рейс" value={values.unitsPerCycle} onChange={(v) => patch('unitsPerCycle', v)} min="0.01" />
        <NumericField label="Погрузка, с" value={values.pickupService} onChange={(v) => patch('pickupService', v)} />
        <NumericField label="Разгрузка, с" value={values.dropoffService} onChange={(v) => patch('dropoffService', v)} />
        <NumericField label="Задержка на поворотах, с" value={values.turnDelay} onChange={(v) => patch('turnDelay', v)} />
        <NumericField label="Заявок одновременно (1 = ровный поток)" value={values.arrivalBurst} onChange={(v) => patch('arrivalBurst', v)} min="1" step="1" />
      </div>
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
      <button type="submit" className="primary-action" disabled={busy}>{busy ? 'Считаю…' : 'Пересчитать по маршруту'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {summary && <div role="status"><p>Статус: <strong>{summary.simulation.status}</strong>{changed ? ' · ввод изменён, нужен повторный пересчёт' : ''}.</p>
      <p>Маршрут с грузом: {summary.simulation.distance_loaded_m ?? '—'} м; пустой ход: {summary.simulation.distance_empty_m ?? '—'} м; ожидание: {summary.simulation.time_wait_s ?? 'не рассчитано'} с; цикл: {summary.simulation.cycle_s ?? 'не рассчитан'} с.</p>
      {summary.simulation.shared_lane && <p>Узкий участок: среднее ожидание {summary.simulation.shared_lane.mean_wait_s} с; проездов {summary.simulation.shared_lane.events}; пропускная способность {summary.simulation.shared_lane.capacity_per_hour} рейсов/ч.</p>}
      <p>Парк: {summary.simulation.fleet_required ?? 'не рассчитан'}; NPV покупки этой работы: {summary.npv ?? 'не рассчитан'} ₽. Флаги: {summary.simulation.flags.join(', ')}.</p>
    </div>}
  </section>;
}
