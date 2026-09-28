import { facilityRoute } from '../../../robcraft/src/integration/facility-playback.js';

const SCALE = 18;
const path = points => points.map((p, i) => `${i ? 'L' : 'M'} ${p.x * SCALE} ${p.y * SCALE}`).join(' ');

export default function Facility2DPlan({ scene, frame, selectedZoneId }) {
  const index = Math.max(0, scene.plans.findIndex(plan => plan.zoneId === selectedZoneId));
  const plan = scene.plans[index], current = frame.zones[index];
  if (!plan) return <p>Для этой зоны нет схемы процесса.</p>;
  const clinic = plan.template === 'hospital';
  return <div className="facility-plan">
    <div className="facility-plan-heading"><strong>{clinic ? 'Клиника · доставка питания' : 'Аэропорт · уборка терминала'}</strong>
      <span>{plan.robots.length === 1 ? '1 робот' : `${plan.robots.length} роботов`} · {current.open ? 'Рабочее окно' : 'Перерыв по графику'}</span></div>
    <svg viewBox="-18 -25 900 640" role="img" aria-label={clinic ? 'Вид сверху: пищеблок, коридор и отделения клиники' : 'Вид сверху: регистрация, ожидание и выходы аэропорта'}>
      <defs><pattern id="facility-floor-grid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M 18 0 L 0 0 0 18" fill="none" stroke="#203c46" strokeWidth=".5" /></pattern></defs>
      <rect x="0" y="0" width="864" height="576" fill="#102831" stroke="#80a4ad" strokeWidth="4" />
      {plan.areas.map(area => <g key={area.id}>
        <rect x={area.x * SCALE} y={area.y * SCALE} width={area.width * SCALE} height={area.height * SCALE} rx="5" fill={area.id === 'corridor' || area.id === 'service' ? '#203d48' : '#17333c'} stroke="#345866" />
        <text x={(area.x + area.width / 2) * SCALE} y={(area.y + .95) * SCALE} textAnchor="middle" fill="#d6edf0" fontSize="12">{area.label}</text>
      </g>)}
      <rect width="864" height="576" fill="url(#facility-floor-grid)" pointerEvents="none" />
      {plan.furniture.map((item, i) => <g key={i}><rect x={item.x * SCALE} y={item.y * SCALE} width={item.width * SCALE} height={item.height * SCALE} rx="4" fill={item.type === 'bed' ? '#aac7d5' : '#547e8b'} stroke="#d1e3e6" />
        {item.type === 'bed' && <rect x={(item.x + .2) * SCALE} y={(item.y + .2) * SCALE} width="10" height="21" rx="2" fill="#ecf5f7" />}</g>)}
      {plan.walls.map((wall, i) => <rect key={i} x={wall.x * SCALE} y={wall.y * SCALE} width={wall.width * SCALE} height={wall.height * SCALE} fill="#9ab5bb" />)}
      {plan.robots.map(robot => {
        const live = current.robots[robot.ordinal];
        const route = live?.route || facilityRoute(plan, robot.ordinal);
        return <g key={robot.id} opacity=".45"><path d={path(clinic ? route.outbound : [...route.outbound, ...route.work])} fill="none" stroke={clinic ? '#59d9f4' : '#68e5bc'} strokeWidth="2" strokeDasharray="6 6" />
          <circle cx={route.handoff.x * SCALE} cy={route.handoff.y * SCALE} r="5" fill="#f4c67a" /></g>;
      })}
      {current.robots.filter(robot => robot.cleaning).map(robot => <path key={`trail-${robot.id}`} d={path(robot.route.work)} stroke="#38d7af" strokeWidth="15" fill="none" opacity=".12" />)}
      {current.robots.map(robot => <g key={robot.id} transform={`translate(${robot.x * SCALE} ${robot.y * SCALE})`}>
        <title>{`${robot.ordinal + 1}: ${robot.stageLabel} · ${robot.areaLabel}`}</title>
        {robot.cleaning && <circle r="18" fill="#49e3b3" opacity=".25" />}
        <g transform={`rotate(${-robot.yaw * 180 / Math.PI})`}><rect x="-9" y="-10" width="18" height="20" rx="5" fill={robot.stage === 'WAITING' || robot.stage === 'OFF_SHIFT' ? '#718793' : '#5ee8cc'} stroke="#071c29" strokeWidth="2" /><path d="M -4 6 L 0 11 L 4 6" fill="none" stroke="#071c29" strokeWidth="2" /></g>
        {robot.carrying && <rect x="-5" y="-7" width="10" height="7" fill="#f5bc67" />}
        <text x="0" y="-16" textAnchor="middle" fill="#fff" fontWeight="700" fontSize="12">{robot.ordinal + 1}</text>
      </g>)}
    </svg>
    <div className="facility-operations" aria-label="Текущие действия роботов">
      {current.robots.slice(0, 12).map(robot => <div key={robot.id}><strong>Робот {robot.ordinal + 1}</strong><span>{robot.stageLabel}</span><small>{robot.areaLabel}{robot.carrying ? ` · ${robot.units} порций` : ''}</small>{Number.isFinite(robot.nextStartSeconds) && <small>Следующее задание через {Math.ceil((robot.nextStartSeconds - current.elapsedSeconds) / 60)} мин модели</small>}</div>)}
      {current.robots.length > 12 && <p>Все {current.robots.length} роботов показаны на плане.</p>}
      {current.reason && <p>{current.reason}</p>}
    </div>
    <p className="simulation-schematic-note">{clinic ? 'Питание поступает с раздачи, проходит по коридору в отделение; после передачи робот возвращается.' : 'Роботы убирают полосы открытого пола в разных частях терминала, затем переходят к следующему участку.'} План условный. Площадь, длина маршрута и результаты расчёта берутся из сохранённых данных. Действия восстановлены по равномерному поступлению заданий и длительности обслуживания; это визуальное воспроизведение, не журнал событий C23.</p>
  </div>;
}
