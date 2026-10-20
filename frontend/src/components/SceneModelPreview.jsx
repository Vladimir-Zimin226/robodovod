import { useEffect, useMemo, useRef, useState } from 'react';
import { buildSceneViews, isoProjection, sceneForKind, sceneWithSimulation, topProjection } from '../sceneModel.js';
import { loadSceneFloorTexture, loadSceneMeshes, SceneRenderer3D } from '../sceneRenderer3D.js';

const COLORS = { CHARGE: '#17a579', PICKUP: '#e8a52c', DROPOFF: '#d65b65', SHARED_LANE: '#8257bd' };
const SCENE_NAMES = { warehouse: 'Склад', airport: 'Аэропорт', clinic: 'Клиника' };
const MATERIALS = {
  pallet_rack: '#447593', conveyor: '#535e6b', baggage_cart: '#6892a4',
  aircraft_marker: '#b3bfca', hospital_bed: '#83acc0', nurse_desk: '#a99481',
};

function points(values, project, z = 0) {
  return values.map((point) => project([point[0], point[1], point[2] ?? z]).map((n) => n.toFixed(2)).join(',')).join(' ');
}

function TopView({ scene, view, pose }) {
  const projection = topProjection(scene);
  return <svg className="scene-preview-svg" viewBox={`0 0 ${projection.width} ${projection.height}`}
    role="img" aria-label={`План сверху: ${scene.scene_id}`}>
    <rect x="0" y="0" width={projection.width} height={projection.height} fill="#e9f0ef" />
    {Array.from({ length: Math.ceil(scene.bounds.width_m / 5) + 1 }, (_, i) => <line key={`x${i}`}
      x1={projection.point([i * 5, 0])[0]} x2={projection.point([i * 5, 0])[0]}
      y1="0" y2={projection.height} stroke="#d2dede" strokeWidth="0.7" />)}
    {Array.from({ length: Math.ceil(scene.bounds.length_m / 5) + 1 }, (_, i) => <line key={`y${i}`}
      x1="0" x2={projection.width} y1={projection.point([0, i * 5])[1]}
      y2={projection.point([0, i * 5])[1]} stroke="#d2dede" strokeWidth="0.7" />)}
    {view.objects.map(({ id, corners }) => {
      const object = scene.objects.find((item) => item.instance_id === id);
      return <polygon key={id} data-instance-id={id} points={points(corners, projection.point)}
        fill={MATERIALS[object.asset_id] || '#647b87'} stroke="#315469" strokeWidth="1" />;
    })}
    {view.routes.map(({ id, points: route }) => <polyline key={id} data-route-id={id}
      points={points(route, projection.point)} fill="none" stroke="#176fb3" strokeWidth="2.4" strokeDasharray="5 3" />)}
    {view.zones.map(({ id, polygon }) => {
      const zone = scene.zones.find((item) => item.zone_id === id);
      const [x, y] = projection.point(zone.center_xy_m);
      return <g key={id} data-zone-id={id}><polygon points={points(polygon, projection.point)}
        fill={COLORS[zone.kind]} fillOpacity="0.14" stroke={COLORS[zone.kind]} strokeWidth="2" />
        <text x={x + 8} y={zone.kind === 'PICKUP' ? y + 17 : y - 7} fontSize="11" fill="#203b48" paintOrder="stroke" stroke="#e9f0ef" strokeWidth="3">{zone.name}</text></g>;
    })}
    {pose && <g data-robot-pose={`${pose[0].toFixed(2)},${pose[1].toFixed(2)}`}>
      <circle cx={projection.point(pose)[0]} cy={projection.point(pose)[1]} r="9" fill="#f1d36b" stroke="#172a38" strokeWidth="3" />
      <circle cx={projection.point(pose)[0]} cy={projection.point(pose)[1]} r="3" fill="#172a38" />
    </g>}
    <line x1="20" y1={projection.height - 14} x2={20 + projection.scale * 5} y2={projection.height - 14} stroke="#183d51" strokeWidth="2" />
    <text x="20" y={projection.height - 20} fontSize="10" fill="#183d51">5 м</text>
  </svg>;
}

function IsoView({ scene, view }) {
  const projection = isoProjection(scene);
  const ground = [[0, 0], [scene.bounds.width_m, 0], [scene.bounds.width_m, scene.bounds.length_m], [0, scene.bounds.length_m]];
  const sorted = [...view.objects].sort((a, b) => {
    const pa = scene.objects.find((item) => item.instance_id === a.id).position_m;
    const pb = scene.objects.find((item) => item.instance_id === b.id).position_m;
    return pa[0] + pa[1] - pb[0] - pb[1];
  });
  return <svg className="scene-preview-svg" viewBox={`0 0 ${projection.width} ${projection.height}`}
    role="img" aria-label={`Изометрическая проекция: ${scene.scene_id}`}>
    <rect width={projection.width} height={projection.height} fill="#e9f0ef" />
    <polygon points={points(ground, projection.point)} fill="#dce8e6" stroke="#91aaa9" strokeWidth="1.5" />
    {view.routes.map(({ id, points: route }) => <polyline key={id} data-route-id={id}
      points={points(route, projection.point, 0.04)} fill="none" stroke="#176fb3" strokeWidth="2.5" strokeDasharray="5 3" />)}
    {view.zones.map(({ id, polygon }) => {
      const zone = scene.zones.find((item) => item.zone_id === id);
      return <polygon key={id} data-zone-id={id} points={points(polygon, projection.point, 0.03)}
        fill={COLORS[zone.kind]} fillOpacity="0.25" stroke={COLORS[zone.kind]} strokeWidth="2" />;
    })}
    {sorted.map(({ id, base, top }) => {
      const object = scene.objects.find((item) => item.instance_id === id);
      const color = MATERIALS[object.asset_id] || '#647b87';
      return <g key={id} data-instance-id={id}>
        <polygon points={points([base[0], base[1], top[1], top[0]], projection.point)} fill={color} opacity="0.72" />
        <polygon points={points([base[1], base[2], top[2], top[1]], projection.point)} fill={color} opacity="0.86" />
        <polygon points={points(top, projection.point)} fill={color} stroke="#315469" strokeWidth="0.8" />
      </g>;
    })}
  </svg>;
}

function ThreeView({ scene, view, pose }) {
  const canvas = useRef(null);
  const poseBadge = useRef(null);
  const renderer = useRef(null);
  const [preset, setPreset] = useState('detail');
  const [expanded, setExpanded] = useState(false);
  const [load, setLoad] = useState({ scene: null, ready: false, floor: false, error: '' });
  const ready = load.scene === scene && load.ready;
  const fallback = load.scene === scene ? load.error : '';
  useEffect(() => {
    let active = true;
    try {
      renderer.current = new SceneRenderer3D(canvas.current);
      Promise.all([loadSceneMeshes(scene), loadSceneFloorTexture(scene).catch(() => null)]).then(([meshes, floor]) => {
        if (!active) return;
        renderer.current.setMeshes(meshes);
        if (floor) renderer.current.setFloorTexture(floor);
        setLoad({ scene, ready: true, floor: Boolean(floor), error: '' });
      }).catch((error) => { if (active) setLoad({ scene, ready: false, floor: false, error: error.message }); });
    } catch (error) {
      queueMicrotask(() => { if (active) setLoad({ scene, ready: false, floor: false, error: error.message }); });
    }
    return () => { active = false; renderer.current?.dispose(); renderer.current = null; };
  }, [scene]);
  useEffect(() => {
    if (ready && !fallback) {
      const point = renderer.current?.render(scene, preset, pose);
      if (poseBadge.current && point) {
        poseBadge.current.style.left = `${canvas.current.offsetLeft + point[0]}px`;
        poseBadge.current.style.top = `${canvas.current.offsetTop + point[1]}px`;
      }
    }
  }, [scene, preset, ready, fallback, expanded, pose]);
  useEffect(() => {
    if (!expanded) return undefined;
    const close = (event) => { if (event.key === 'Escape') setExpanded(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [expanded]);
  const ids = (entries, key) => entries.map((item) => item[key]).sort().join(',');
  return <div className={`scene-preview-3d${expanded ? ' scene-preview-3d--expanded' : ''}`}>
    <div className="scene-preview-camera" aria-label="Камера 3D">
      {[['detail', 'Вблизи'], ['overview', 'Обзор'], ['isometric', 'Изометрия'], ['top', 'Сверху']].map(([key, label]) =>
        <button key={key} type="button" aria-pressed={preset === key} onClick={() => setPreset(key)}>{label}</button>)}
      <button type="button" onClick={() => setExpanded((value) => !value)}
        aria-label={expanded ? 'Закрыть полноэкранную 3D-сцену' : 'Развернуть 3D-сцену'}>
        {expanded ? 'Свернуть' : 'Развернуть 3D'}
      </button>
    </div>
    <canvas ref={canvas} className="scene-preview-canvas" role="img"
      aria-label={`3D-сцена GLB: ${scene.scene_id}`}
      data-instance-ids={ids(scene.objects, 'instance_id')}
      data-zone-ids={ids(scene.zones, 'zone_id')}
      data-route-ids={ids(scene.routes, 'route_id')}
      data-glb-status={fallback ? 'FALLBACK' : ready ? 'READY' : 'LOADING'}
      data-floor-texture-status={ready ? load.floor ? 'READY' : 'FALLBACK' : 'LOADING'} />
    {pose && ready && <span ref={poseBadge} className="scene-robot-badge" aria-label="Положение движущегося робота в 3D">Робот</span>}
    {fallback && <div className="scene-preview-fallback"><p>3D недоступно: {fallback}. Схема ниже сохраняет те же координаты.</p>
      <IsoView scene={scene} view={view} /></div>}
    {!fallback && !ready && <p role="status">Загружаются локальные GLB-модели…</p>}
  </div>;
}

export default function SceneModelPreview({ kind, overlay, pose }) {
  const [mobileView, setMobileView] = useState('3d');
  const source = sceneForKind(kind);
  const scene = useMemo(() => source ? sceneWithSimulation(source, overlay?.request, overlay?.result) : null,
    [source, overlay?.request, overlay?.result]);
  const views = useMemo(() => scene ? buildSceneViews(scene) : null, [scene]);
  if (!scene) return <p>Для этого типа объекта демосцена отсутствует.</p>;
  return <section className="scene-preview" aria-label="Единая геометрия сцены">
    <p><strong>Условный шаблон «{SCENE_NAMES[scene.scene_id]}»</strong> · {scene.bounds.width_m} × {scene.bounds.length_m} м · {scene.objects.length} объектов · {scene.zones.length} зоны</p>
    <div className="scene-preview-mobile-switch" role="group" aria-label="Вид сцены">
      <button type="button" aria-pressed={mobileView === '3d'} onClick={() => setMobileView('3d')}>3D-сцена</button>
      <button type="button" aria-pressed={mobileView === '2d'} onClick={() => setMobileView('2d')}>2D-план</button>
    </div>
    <div className="scene-preview-grid" data-mobile-view={mobileView}>
      <figure className="scene-preview-hero"><ThreeView scene={scene} view={views.iso} pose={pose} /><figcaption>3D · модели текущей демонстрационной сцены</figcaption></figure>
      <figure className="scene-preview-plan"><TopView scene={scene} view={views.top} pose={pose} /><figcaption>2D · те же объекты и маршрут</figcaption></figure>
    </div>
    <p className="scene-preview-evidence">Демонстрационный план · требуется проверка реального объекта. 2D и 3D читают один SceneModel. {overlay ? `Серверный статус маршрута: ${overlay.result.status}. Локальные правки не сохранены.` : 'Исходный маршрут ещё не проверен на коллизии.'}</p>
    <p className="scene-preview-legend"><span style={{ color: COLORS.CHARGE }}>● Зарядка</span><span style={{ color: COLORS.PICKUP }}>● Отбор</span><span style={{ color: COLORS.DROPOFF }}>● Доставка</span><span style={{ color: COLORS.SHARED_LANE }}>▭ Узкий участок</span><span style={{ color: '#176fb3' }}>┄ Условный маршрут</span></p>
  </section>;
}
