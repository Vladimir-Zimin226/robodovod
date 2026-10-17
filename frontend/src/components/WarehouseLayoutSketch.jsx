import { useEffect, useMemo, useState } from 'react';
import FloorplanUploader from './FloorplanUploader';
import { emptyFacilityLayout, exampleFacilityLayout, estimateFacilityRoute, itemSize, layoutFingerprint, parseFacilityLayoutDraft } from '../facilityLayout';
import WarehouseLayoutVolume from './WarehouseLayoutVolume';
import DxfLayoutImporter from './DxfLayoutImporter';

const TOOLS = [
  ['rack', 'Стеллаж'], ['obstacle', 'Препятствие'], ['no_go', 'Запретная зона'],
  ['aisle', 'Проход'], ['charger', 'Зарядка'], ['pickup', 'Приёмка'], ['dropoff', 'Отгрузка'],
  ['receiving', 'Зона приёмки'], ['picking', 'Комплектация'], ['packing', 'Упаковка'],
  ['shipping', 'Зона отгрузки'], ['staging', 'Буфер паллет'],
];
const AREA_LABELS = { receiving: 'ПРИЁМКА', picking: 'КОМПЛЕКТАЦИЯ', packing: 'УПАКОВКА',
  shipping: 'ОТГРУЗКА', staging: 'БУФЕР' };
const ITEM_FILL = { rack: '#57765b', obstacle: '#a77363', no_go: '#be6057', aisle: '#284d57',
  charger: '#7289c7', pickup: '#e7b66b', dropoff: '#77d9cc', receiving: '#2e5e68',
  picking: '#485975', packing: '#645276', shipping: '#38635d', staging: '#746347' };
const itemKey = (item, index) => item.id || `legacy-${index}`;
const EMPTY_LAYOUT = emptyFacilityLayout();
const originLabel = (provenance) => provenance === 'ASSUMED' ? 'учебное допущение'
  : provenance === 'PROVIDED' ? 'импортировано из DXF, масштаб подтверждён пользователем' : 'нарисовано пользователем';

export default function WarehouseLayoutSketch({ value, onChange, processes = [], onApplyDistance }) {
  const layout = value || EMPTY_LAYOUT;
  const [tool, setTool] = useState('rack');
  const [x, setX] = useState(10);
  const [y, setY] = useState(10);
  const [expanded, setExpanded] = useState(false);
  const [view, setView] = useState('plan');
  const [selectedId, setSelectedId] = useState(null);
  const [targetProcessId, setTargetProcessId] = useState('');
  const [appliedRoute, setAppliedRoute] = useState(null);
  const [importError, setImportError] = useState('');
  const [animationTime, setAnimationTime] = useState(0);
  const width = Number(layout.width_m) || 60;
  const depth = Number(layout.depth_m) || 36;
  const items = layout.items || [];
  const robotWidth = Number(layout.robot_width_m) || 1;
  const animateRoute = typeof window !== 'undefined' && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const route = useMemo(() => estimateFacilityRoute(layout, { robotWidthM: robotWidth }), [layout, robotWidth]);
  useEffect(() => {
    if (!expanded || route.status !== 'READY' || !animateRoute) return undefined;
    const timer = window.setInterval(() => setAnimationTime((current) => (current + .1) % 24), 100);
    return () => window.clearInterval(timer);
  }, [expanded, route.status, animateRoute]);
  const animationIndex = route.status === 'READY' ? Math.min(route.path.length - 1,
    Math.floor((animationTime < 12 ? animationTime : 24 - animationTime) / 12 * (route.path.length - 1))) : 0;
  const robotPoint = route.status === 'READY' ? route.path[animationIndex] : null;
  const appliedProcess = processes.find((process) => process.distance && process.distanceFromPlan === layoutFingerprint(layout));
  const selectedIndex = items.findIndex((item, index) => itemKey(item, index) === selectedId);
  const selected = items[selectedIndex];
  const routeChanged = appliedRoute && appliedRoute.fingerprint !== layoutFingerprint(layout);
  const pickup = items.find((item) => item.kind === 'pickup');
  const dropoff = items.find((item) => item.kind === 'dropoff');
  const put = (kind, rawX, rawY) => {
    const [itemWidth, itemDepth] = itemSize({ kind });
    const next = { id: `item-${Date.now()}-${items.length}`, kind, provenance: 'DRAWN',
      x: Math.max(0, Math.min(width - itemWidth, Math.round(rawX * 2) / 2)),
      y: Math.max(0, Math.min(depth - itemDepth, Math.round(rawY * 2) / 2)) };
    onChange({ ...layout, items: [...items.filter((item) => !['pickup', 'dropoff'].includes(kind) || item.kind !== kind), next] });
    setSelectedId(next.id);
  };
  const placeFromPointer = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    put(tool, (event.clientX - bounds.left) / bounds.width * width, (event.clientY - bounds.top) / bounds.height * depth);
  };
  const saveJson = () => {
    const clean = { ...layout, imageData: null, image_not_embedded: Boolean(layout.imageData),
      route_preview: route.status === 'READY' ? { length_m: route.length_m, robot_width_m: route.robot_width_m,
        clearance_m: route.clearance_m, status: 'LOCAL_ESTIMATE_ONLY' } : null };
    const url = URL.createObjectURL(new Blob([JSON.stringify(clean, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'warehouse-layout-draft.json'; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className="warehouse-layout-sketch" aria-label="План склада">
    <div className="warehouse-layout-heading"><div><h3>План склада</h3><p>Откройте конструктор, чтобы загрузить DXF из AutoCAD, изображение плана или расставить объекты. Есть учебный DXF для пробы.</p></div>
      <button type="button" onClick={() => setExpanded((current) => !current)} aria-expanded={expanded}>{expanded ? 'Свернуть план' : 'Открыть конструктор'}</button></div>
    {expanded && <>
      <FloorplanUploader onResult={(data) => { setAppliedRoute(null); onChange({ ...emptyFacilityLayout(), source: 'IMAGE_REFERENCE', imageData: data.imageData,
        width_m: Math.max(10, Math.round(data.width_m * 10) / 10), depth_m: Math.max(10, Math.round(data.height_m * 10) / 10),
        zones: data.zoneMappings || [] }); }} />
      <DxfLayoutImporter onResult={(data) => { setAppliedRoute(null); setSelectedId(null); onChange(data); }} />
      <label className="warehouse-layout-json-import">Открыть ранее сохранённую схему JSON<input type="file" accept=".json,application/json" onChange={async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        try { if (file.size > 256_000) throw new Error('Файл схемы слишком большой.');
          const imported = parseFacilityLayoutDraft(await file.text()); onChange(imported); setSelectedId(null); setAppliedRoute(null); setImportError(''); }
        catch (failure) { setImportError(failure.message); }
        event.target.value = '';
      }} /></label>
      {importError && <p className="warehouse-dxf-error" role="alert">{importError}</p>}
      <div className="warehouse-layout-dimensions">
        <label>Ширина, м<input type="number" min="10" max="500" value={width} onChange={(event) => onChange({ ...layout, width_m: Math.max(10, Math.min(500, Number(event.target.value) || 10)) })} /></label>
        <label>Глубина, м<input type="number" min="10" max="500" value={depth} onChange={(event) => onChange({ ...layout, depth_m: Math.max(10, Math.min(500, Number(event.target.value) || 10)) })} /></label>
        <label>Ширина робота, м<input type="number" min="0.5" max="3" step="0.1" value={robotWidth} onChange={(event) => onChange({ ...layout, robot_width_m: Math.max(.5, Math.min(3, Number(event.target.value) || 1)) })} /></label>
        <button type="button" onClick={() => { onChange(emptyFacilityLayout()); setSelectedId(null); setAppliedRoute(null); }}>Новая пустая схема</button>
        <button type="button" onClick={() => { onChange(exampleFacilityLayout()); setSelectedId(null); setAppliedRoute(null); }}>Показать учебный план</button>
      </div>
      <div className="warehouse-layout-tools" role="group" aria-label="Что поставить на плане">{TOOLS.map(([kind, label]) =>
        <button type="button" key={kind} aria-pressed={tool === kind} onClick={() => setTool(kind)}>{label}</button>)}</div>
      <div className="warehouse-layout-views" role="tablist" aria-label="Вид планировки"><button type="button" role="tab" aria-selected={view === 'plan'} onClick={() => setView('plan')}>План сверху</button><button type="button" role="tab" aria-selected={view === 'volume'} onClick={() => setView('volume')}>Объёмный эскиз</button></div>
      <div className={`warehouse-layout-map${view === 'volume' ? ' is-volume' : ''}`} style={view === 'plan' ? { aspectRatio: `${width} / ${depth}` } : undefined}>
        {view === 'volume' ? <WarehouseLayoutVolume layout={layout} route={route} robotPoint={animateRoute ? robotPoint : null} /> : <svg viewBox={`0 0 ${width} ${depth}`} role="img" aria-label={`Схема склада ${width} на ${depth} метров`} onClick={placeFromPointer}>
          <defs><pattern id="warehouse-draft-grid" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M5 0H0V5" fill="none" stroke="#43707a" strokeWidth=".12" /></pattern>
            <pattern id="warehouse-rack-deck" width="1" height="1" patternUnits="userSpaceOnUse"><path d="M0 0H1M0 .55H1" stroke="#c48e4c" strokeWidth=".09" /></pattern>
            <pattern id="warehouse-obstacle-hatch" width=".8" height=".8" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><path d="M0 0V.8" stroke="#edb9a4" strokeWidth=".15" /></pattern></defs>
          <rect width={width} height={depth} fill="#102a32" />
          {layout.imageData && <image href={layout.imageData} x="0" y="0" width={width} height={depth} preserveAspectRatio="none" opacity=".5" />}
          <rect width={width} height={depth} fill="url(#warehouse-draft-grid)" />
          {route.status === 'READY' && <polyline points={route.path.map((point) => `${point.x},${point.y}`).join(' ')} fill="none" stroke="#66f5cb" strokeWidth=".55" strokeLinecap="round" strokeLinejoin="round" />}
          {robotPoint && animateRoute && <circle cx={robotPoint.x} cy={robotPoint.y} r=".7" fill="#d8ff83" stroke="#102a32" strokeWidth=".2" />}
          {pickup && dropoff && route.status !== 'READY' && <path d={`M ${pickup.x + .5} ${pickup.y + .5} L ${dropoff.x + .5} ${dropoff.y + .5}`} fill="none" stroke="#f0a56f" strokeWidth=".3" strokeDasharray=".8 .6" />}
          {items.map((item, index) => { const [w, h] = itemSize(item); return <g key={itemKey(item, index)} onClick={(event) => { event.stopPropagation(); setSelectedId(itemKey(item, index)); }}>
            <rect x={item.x} y={item.y} width={w} height={h} rx=".2" fill={ITEM_FILL[item.kind] || ITEM_FILL.obstacle} fillOpacity={AREA_LABELS[item.kind] ? '.4' : '1'} stroke={selectedId === itemKey(item, index) ? '#fdf789' : item.provenance === 'ASSUMED' ? '#e8b778' : item.provenance === 'PROVIDED' ? '#75d9f4' : '#eff8ee'} strokeWidth={selectedId === itemKey(item, index) ? '.35' : '.15'} />
            {item.kind === 'rack' && <><rect x={item.x + .18} y={item.y + .18} width={Math.max(0, w - .36)} height={Math.max(0, h - .36)} fill="url(#warehouse-rack-deck)" stroke="#d19d59" strokeWidth=".1" />
              {[.2, .5, .8].map((fraction) => <line key={fraction} x1={item.x + w * fraction} y1={item.y + .1} x2={item.x + w * fraction} y2={item.y + h - .1} stroke="#223c3c" strokeWidth=".15" />)}</>}
            {['obstacle', 'no_go'].includes(item.kind) && <rect x={item.x} y={item.y} width={w} height={h} fill="url(#warehouse-obstacle-hatch)" opacity=".55" />}
            {AREA_LABELS[item.kind] && <text x={Number(item.x) + w / 2} y={Number(item.y) + h / 2} textAnchor="middle" dominantBaseline="middle" fill="#eaf8f1" fontSize="1.2" fontWeight="700" pointerEvents="none">{AREA_LABELS[item.kind]}</text>}
            {['pickup', 'dropoff'].includes(item.kind) && <text x={item.x + .5} y={item.y - .25} textAnchor="middle" fill="#fff" fontSize="1.4">{item.kind === 'pickup' ? 'П' : 'О'}</text>}
          </g>; })}
        </svg>}
      </div>
      <div className="warehouse-layout-coordinates"><label>X, м<input type="number" min="0" max={width} value={x} onChange={(event) => setX(Number(event.target.value))} /></label><label>Y, м<input type="number" min="0" max={depth} value={y} onChange={(event) => setY(Number(event.target.value))} /></label><button type="button" onClick={() => put(tool, x, y)}>Добавить в координатах</button></div>
      <div className="warehouse-layout-legend"><span><i className="route" /> проверенный путь</span><span><i className="provided" /> импорт DXF</span><span><i className="assumed" /> учебное допущение</span><span><i className="drawn" /> нанесено пользователем</span><span>«Проход» — ориентир; проходимость определяют препятствия и габарит робота.</span></div>
      {selected && <div className="warehouse-layout-selected"><strong>Выбрано: {TOOLS.find(([kind]) => kind === selected.kind)?.[1]}</strong><span>Источник: {originLabel(selected.provenance)}</span>
        <label>Ширина, м<input type="number" min="0.5" max={width} step="0.5" value={itemSize(selected)[0]} onChange={(event) => onChange({ ...layout, items: items.map((item, index) => index === selectedIndex ? { ...item, width_m: Math.max(.5, Math.min(width - Number(item.x), Number(event.target.value) || .5)) } : item) })} /></label>
        <label>Глубина, м<input type="number" min="0.5" max={depth} step="0.5" value={itemSize(selected)[1]} onChange={(event) => onChange({ ...layout, items: items.map((item, index) => index === selectedIndex ? { ...item, depth_m: Math.max(.5, Math.min(depth - Number(item.y), Number(event.target.value) || .5)) } : item) })} /></label>
        <button type="button" onClick={() => { onChange({ ...layout, items: items.filter((_, index) => index !== selectedIndex) }); setSelectedId(null); }}>Удалить объект</button></div>}
      <div className={`warehouse-layout-route route-${route.status.toLowerCase()}`} role="status">
        <strong>{route.status === 'READY' ? `Проходимый путь: ${route.length_m} м` : route.status === 'BLOCKED' ? 'Проезд не найден' : 'Маршрут ещё не готов'}</strong>
        <span>{route.status === 'READY' ? `Напрямую ${route.straight_m} м · обход ${Math.max(0, Number((route.length_m - route.straight_m).toFixed(1)))} м · ширина робота ${robotWidth} м + безопасный зазор 0,25 м с каждой стороны.` : route.reason}</span>
        <small>Локальная проверка сеткой {route.step_m?.toFixed(2) || '0,50'} м. Анимация показывает путь, не скорость; встречный поток и время передачи здесь не моделируются.</small>
        {routeChanged && <span className="warehouse-layout-delta">После изменения плана: {route.status === 'READY' ? `${route.length_m >= appliedRoute.length_m ? '+' : '−'}${Math.abs(Number((route.length_m - appliedRoute.length_m).toFixed(1)))} м к ранее применённому плечу ${appliedRoute.length_m} м.` : 'прежний маршрут больше не проходим.'} Нужен новый серверный расчёт.</span>}
        {route.status === 'READY' && processes.length > 0 && <div className="warehouse-layout-apply"><label>Для процесса<select value={targetProcessId || processes[0].processId} onChange={(event) => setTargetProcessId(event.target.value)}>{processes.map((process) => <option key={process.processId} value={process.processId}>{process.label}</option>)}</select></label><button type="button" onClick={() => { setAppliedRoute({ fingerprint: layoutFingerprint(layout), length_m: route.length_m }); onApplyDistance?.(targetProcessId || processes[0].processId); }}>Применить расстояние к расчёту</button></div>}
        {appliedProcess && <small className="warehouse-layout-applied">✓ {appliedProcess.distance} м передано во входы «{appliedProcess.label}». После проверки остальных полей запустите новый расчёт.</small>}
      </div>
      <div className="warehouse-layout-footer"><span>{items.length} объектов · {layout.source === 'IMAGE_REFERENCE' ? 'подложка из изображения' : layout.source === 'DXF_TRACE' ? 'контуры из DXF' : layout.source === 'ASSUMED_REFERENCE' ? 'сгенерировано по открытым референсам' : 'схема нарисована здесь'}</span><div><button type="button" onClick={() => { onChange({ ...layout, items: items.slice(0, -1) }); setSelectedId(null); }} disabled={!items.length}>Отменить последнее</button><button type="button" onClick={saveJson}>Скачать схему JSON</button></div></div>
      {layout.source === 'ASSUMED_REFERENCE' && <details className="warehouse-layout-references"><summary>Источники учебной структуры</summary><p>Размеры 72 × 48 м, положение стеллажей, ширина проходов и маршрут придуманы для демонстрации. Зоны и логика потока опираются на открытые материалы:</p><ul><li><a href="https://www.interlakemecalux.com/warehouse-manual/warehouse-design/warehouse-layout" target="_blank" rel="noreferrer">Interlake Mecalux: функциональные зоны склада</a></li><li><a href="https://www.warehouse-science.com/wh/book/editions/wh-sci-0.96.pdf" target="_blank" rel="noreferrer">Warehouse &amp; Distribution Science: U-flow и flow-through</a></li><li><a href="https://og.mhi.org/rmi" target="_blank" rel="noreferrer">MHI/RMI: планирование стеллажной системы</a></li></ul></details>}
      <p className="warehouse-layout-caution">Длина маршрута — предварительная оценка по отмеченным препятствиям. После явного применения она станет входом нового серверного расчёта; изменение плана сбросит это расстояние и потребует повторного применения. Подложка сама не распознаёт стены. Из DWG экспортируйте DXF или изображение; импортируются только подтверждённые прямые контуры.</p>
    </>}
  </section>;
}
