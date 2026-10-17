import { useState } from 'react';
import { facilityRoute } from '../../../robcraft/src/integration/facility-playback.js';
import { safeRoute } from '../../../robcraft/src/integration/safe-playback-v2.js';
import { PROCESS_DEFINITIONS } from '../processRoleIntakeV2';
import { cargoLabel } from '../cargoLabel';

const SCALE = 18;
const path = points => points.map((p, i) => `${i ? 'L' : 'M'} ${p.x * SCALE} ${p.y * SCALE}`).join(' ');

export default function Facility2DPlan({ scene, frame, selectedZoneId, compact = false, selectedOrdinal = null, onSelectRobot }) {
  const [expanded, setExpanded] = useState(false);
  const [allRobots, setAllRobots] = useState(false);
  const index = Math.max(0, scene.plans.findIndex(plan => plan.zoneId === selectedZoneId));
  const plan = scene.plans[index], current = frame.zones[index];
  if (!plan) return <p>Для этой зоны нет схемы процесса.</p>;
  const clinic = plan.template === 'hospital';
  const safe = Boolean(plan.presentationVersion);
  const label = safe ? (PROCESS_DEFINITIONS.find((item) => item.code === plan.processCode)?.label || 'Поддержанный процесс')
    : clinic ? 'Клиника · доставка питания' : 'Аэропорт · уборка терминала';
  const width = plan.width * SCALE, height = plan.height * SCALE;
  const tall = height > width * 1.15;
  const focused = current.robots.find((robot) => robot.ordinal === selectedOrdinal) || current.robots[0];
  const visibleRobots = compact && !allRobots
    ? [...new Map([current.robots[0], current.robots[1], focused].filter(Boolean).map((robot) => [robot.id, robot])).values()]
    : current.robots;
  return <div className={`facility-plan${tall ? ' facility-plan-tall' : ''}${expanded ? ' facility-plan-expanded' : ''}${compact ? ' facility-plan-compact' : ''}`}
    style={{ '--plan-ratio': (width + 36) / (height + 64) }}>
    <div className="facility-plan-heading"><strong>{label}</strong>
      <span>{plan.robots.length === 1 ? '1 робот' : `${plan.robots.length} роботов`} · {current.open ? 'Рабочее окно' : 'Перерыв по графику'}</span>
      {tall && <button type="button" aria-pressed={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'План и действия рядом' : 'Развернуть план'}</button>}</div>
    {focused && <div className="facility-focused-event"><strong>На плане: робот {focused.ordinal + 1}</strong><span>{focused.stageLabel} · {focused.areaLabel}</span><small>Выберите другого робота на схеме или в списке. Положение иллюстративное; очередь и мощность — из сохранённого отчёта.</small></div>}
    <div className="facility-plan-content"><div className="facility-map">
    <svg viewBox={`-18 -25 ${width + 36} ${height + 64}`} role="img" aria-label={`Вид сверху: ${label}`}>
      <defs><pattern id="facility-floor-grid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M 18 0 L 0 0 0 18" fill="none" stroke="#203c46" strokeWidth=".5" /></pattern></defs>
      <rect x="0" y="0" width={width} height={height} fill="#102831" stroke="#80a4ad" strokeWidth="4" />
      {plan.areas.map(area => <g key={area.id}>
        <rect x={area.x * SCALE} y={area.y * SCALE} width={area.width * SCALE} height={area.height * SCALE} rx="5" fill={area.id === 'corridor' || area.id === 'service' ? '#203d48' : '#17333c'} stroke="#345866" />
        <text x={(area.x + area.width / 2) * SCALE} y={(area.y + .95) * SCALE} textAnchor="middle" fill="#d6edf0" fontSize="12">{area.label}</text>
      </g>)}
      <rect width={width} height={height} fill="url(#facility-floor-grid)" pointerEvents="none" />
      {plan.furniture.map((item, i) => <g key={i}><title>{item.robotOrdinal === undefined ? item.type : `Стеллаж ${item.robotOrdinal + 1} · робот ${item.robotOrdinal + 1}`}</title><rect x={item.x * SCALE} y={item.y * SCALE} width={item.width * SCALE} height={item.height * SCALE} rx="4" fill={item.type === 'bed' ? '#aac7d5' : '#547e8b'} stroke="#d1e3e6" />
        {item.type === 'bed' && <rect x={(item.x + .2) * SCALE} y={(item.y + .2) * SCALE} width="10" height="21" rx="2" fill="#ecf5f7" />}
        {item.robotOrdinal !== undefined && <text x={(item.x + item.width / 2) * SCALE} y={(item.y + item.height / 2 + .16) * SCALE} textAnchor="middle" fill="#fff" fontSize="11" fontWeight="700">С{item.robotOrdinal + 1}</text>}</g>)}
      {plan.walls.map((wall, i) => <rect key={i} x={wall.x * SCALE} y={wall.y * SCALE} width={wall.width * SCALE} height={wall.height * SCALE} fill="#9ab5bb" />)}
      {plan.people?.map((person, i) => <circle key={`person-${i}`} cx={person.x * SCALE} cy={person.y * SCALE} r={person.radius * SCALE} fill="#efbb82"><title>{person.label} · выделенная зона ожидания</title></circle>)}
      {plan.homes?.map((home, i) => <rect key={`home-${i}`} x={(home.x - 1) * SCALE} y={(home.y - 1) * SCALE} width={2 * SCALE} height={2 * SCALE} fill="none" stroke="#64868f" strokeDasharray="4 4" />)}
      {plan.robots.map(robot => {
        const live = current.robots[robot.ordinal];
        const route = live?.route || (safe ? safeRoute(plan, robot.ordinal) : facilityRoute(plan, robot.ordinal));
        return <g key={robot.id} opacity={robot.ordinal === focused?.ordinal ? '.85' : '.22'}><path d={path([...(route.toLoad || []), ...route.outbound, ...route.work, ...route.returning])} fill="none" stroke={robot.ordinal === focused?.ordinal ? '#d2ff6d' : clinic ? '#59d9f4' : '#68e5bc'} strokeWidth={robot.ordinal === focused?.ordinal ? '3.5' : '2'} strokeDasharray="6 6" />
          <circle cx={route.handoff.x * SCALE} cy={route.handoff.y * SCALE} r="5" fill="#f4c67a" /></g>;
      })}
      {current.robots.filter(robot => robot.cleaning).map(robot => <path key={`trail-${robot.id}`} d={path(robot.route.work)} stroke="#38d7af" strokeWidth="15" fill="none" opacity=".12" />)}
      {current.robots.map(robot => <g key={robot.id} transform={`translate(${robot.x * SCALE} ${robot.y * SCALE})`}
        role="button" tabIndex="0" aria-label={`Выбрать робота ${robot.ordinal + 1}`} onClick={() => onSelectRobot?.(robot.ordinal === selectedOrdinal ? null : robot.ordinal)}
        onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectRobot?.(robot.ordinal === selectedOrdinal ? null : robot.ordinal); } }}>
        <title>{`${robot.ordinal + 1}: ${robot.stageLabel} · ${robot.areaLabel}`}</title>
        {robot.ordinal === focused?.ordinal && <circle r="25" fill="none" stroke="#d2ff6d" strokeWidth="3" />}
        {robot.cleaning && <circle r="18" fill="#49e3b3" opacity=".25" />}
        <g transform={`rotate(${-robot.yaw * 180 / Math.PI})`}><rect x={-(robot.footprint?.width || 1) * SCALE / 2} y={-(robot.footprint?.length || 1.1) * SCALE / 2} width={(robot.footprint?.width || 1) * SCALE} height={(robot.footprint?.length || 1.1) * SCALE} rx="5" fill={robot.stage === 'WAITING' || robot.stage === 'OFF_SHIFT' ? '#718793' : '#5ee8cc'} stroke="#071c29" strokeWidth="2" /><path d="M -4 6 L 0 11 L 4 6" fill="none" stroke="#071c29" strokeWidth="2" /></g>
        {robot.carrying && <rect x="-5" y="-7" width="10" height="7" fill="#f5bc67" />}
        <text x="0" y="-16" textAnchor="middle" fill="#fff" fontWeight="700" fontSize="12">{robot.ordinal + 1}</text>
      </g>)}
    </svg></div>
    <div className="facility-plan-aside"><div className="facility-operations" aria-label="Текущие действия роботов">
      {visibleRobots.map(robot => <button type="button" key={robot.id} className={robot.ordinal === focused?.ordinal ? 'is-focused' : ''} aria-pressed={robot.ordinal === selectedOrdinal} onClick={() => onSelectRobot?.(robot.ordinal === selectedOrdinal ? null : robot.ordinal)}><strong>Робот {robot.ordinal + 1}</strong><span>{robot.stageLabel}</span><small>{robot.waitReason || robot.areaLabel}{robot.carrying ? ` · ${cargoLabel(robot.units, plan.template)}` : ''}</small>{Number.isFinite(robot.nextStartSeconds) && <small>Следующее задание через {Math.ceil((robot.nextStartSeconds - current.elapsedSeconds) / 60)} мин модели</small>}</button>)}
      {current.reason && <p>{current.reason}</p>}
    </div>
    {compact && current.robots.length > 3 && <button className="facility-robots-toggle" type="button" aria-expanded={allRobots} onClick={() => setAllRobots(value => !value)}>{allRobots ? 'Показать только 3 роботов' : `Показать всех ${current.robots.length} роботов`}</button>}
    <p className="simulation-schematic-note">{selectedOrdinal !== null && 'Выбранный робот останется в фокусе при переключении в 3D. Нажмите его повторно, чтобы вернуть автоматическую камеру. '}{plan.warehouseTransport ? 'Каждому роботу выделен свой стеллаж и место отгрузки. Он забирает подготовленную паллету из одной из четырёх точек возле стеллажа, везёт её в отгрузку и возвращается к своему стеллажу. Встречные рейсы разделены по полосам. Зарядка учтена в сохранённой агрегированной паузе: данных о батареях для отдельного графика зарядки нет.' : safe ? 'Раздельные стоянки и направления. Общие проходы и точки передачи бронируются с проверкой всего пути и неподвижных участников.' : clinic ? 'Питание поступает с раздачи, проходит по коридору в отделение; после передачи робот возвращается.' : 'Роботы убирают полосы открытого пола в разных частях терминала.'} План условный. Задания восстановлены по сохранённому спросу, графику и длительности обслуживания. Серверные показатели остаются исходными. Это не сертификация безопасности реального объекта.</p>
    </div></div>
  </div>;
}
