import { useMemo, useState } from 'react';
import { estimateFacilityRoute, itemSize } from '../facilityLayout';
import WarehouseLayoutVolume from './WarehouseLayoutVolume';

const fill = { rack: '#567a60', obstacle: '#a87362', no_go: '#b65355', aisle: '#2c5c66',
  charger: '#7895cb', pickup: '#e6b66a', dropoff: '#73d8c7' };

export default function FacilityLayoutEvidence({ evidence, onRetrySave }) {
  const [view, setView] = useState('plan');
  const { facilityPlan: layout, appliedDistanceM } = evidence;
  const route = useMemo(() => estimateFacilityRoute(layout, { robotWidthM: Number(layout.robot_width_m) || 1 }), [layout]);
  const width = Number(layout.width_m), depth = Number(layout.depth_m);
  const sameDistance = route.status === 'READY' && Math.abs(route.length_m - appliedDistanceM) < .11;
  return <section className="facility-layout-evidence" aria-label="Планировка, связанная с текущим расчётом">
    <div className="facility-layout-evidence-heading"><div><span className="guest-demo-step">ПЛАНИРОВКА · ВХОД РАСЧЁТА</span>
      <h2>От плана до числа в расчёте</h2>
      <p>Из этой схемы вы применили предварительную оценку маршрута. Сервер получил расстояние {appliedDistanceM} м. {evidence.saveStatus === 'saved' ? 'Версия схемы сохранена с этим расчётом проекта.' : evidence.saveStatus === 'error' ? 'Версия схемы пока доступна только в этой сессии.' : 'Сохраняем отдельную копию схемы с этим расчётом.'}</p></div>
      <strong>{sameDistance ? `Маршрут ${route.length_m} м` : 'План изменился · перепроверьте вход'}</strong></div>
    <div className="warehouse-layout-views" role="tablist" aria-label="Вид применённой планировки"><button type="button" role="tab" aria-selected={view === 'plan'} onClick={() => setView('plan')}>План сверху</button><button type="button" role="tab" aria-selected={view === 'volume'} onClick={() => setView('volume')}>Объёмный эскиз</button></div>
    <div className="facility-layout-evidence-map">{view === 'volume' ? <WarehouseLayoutVolume layout={layout} route={route} /> :
      <svg viewBox={`0 0 ${width} ${depth}`} role="img" aria-label="План, по которому предварительно оценён маршрут">
        <rect width={width} height={depth} fill="#102a32" />
        {layout.imageData && <image href={layout.imageData} x="0" y="0" width={width} height={depth} preserveAspectRatio="none" opacity=".48" />}
        {route.status === 'READY' && <polyline points={route.path.map(({ x, y }) => `${x},${y}`).join(' ')} fill="none" stroke="#69f5c9" strokeWidth=".6" />}
        {(layout.items || []).map((item, index) => { const [w, h] = itemSize(item); return <rect key={item.id || index} x={item.x} y={item.y} width={w} height={h} rx=".15" fill={fill[item.kind] || fill.obstacle}
          stroke={item.provenance === 'PROVIDED' ? '#75d9f4' : item.provenance === 'ASSUMED' ? '#e8b778' : '#eff8ee'} strokeWidth=".16"><title>{item.kind} · {item.provenance}</title></rect>; })}
      </svg>}</div>
    <p className="facility-layout-evidence-caution">Серверный парк и экономика используют введённые метры. Очередь, пересечения и движения на плане не проверены серверной симуляцией по этой геометрии. Визуализация расчёта ниже остаётся условной сценой.</p>
    {evidence.saveStatus === 'error' && <div className="facility-layout-evidence-save-error" role="alert">{evidence.saveError}<button type="button" onClick={onRetrySave}>Повторить сохранение схемы</button></div>}
    {evidence.saveStatus === 'saved' && <small className="facility-layout-evidence-digest">Контрольная сумма версии схемы: {evidence.layoutDigest}</small>}
  </section>;
}
