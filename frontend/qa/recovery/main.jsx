import { useCallback, useState } from 'react';
import { createRoot } from 'react-dom/client';
import SceneModelPreview from '../../src/components/SceneModelPreview.jsx';
import SceneSimulationControls from '../../src/components/SceneSimulationControls.jsx';
import paths from './paths.json';
import '../../src/index.css';

const kind = new URLSearchParams(location.search).get('kind') || 'warehouse';
const fixture = paths[kind];
const object = kind !== 'warehouse';
const work = { technical_task: 'Перевозка между зонами', unit: 'item',
  process_code: kind === 'airport' ? 'airport_baggage' : 'clinic_medicines',
  selected_position_id: 'SCENARIO_TYPE' };
const input = object ? { roles: [{ role_code: 'transport', works: [work] }] }
  : { roles: [{ role_code: 'forklift_driver' }] };
const row = { simulation: fixture?.result, fleet: fixture?.result.fleet_required,
  npv_rub: null, purchase: { npv_rub: null }, position_id: 'SCENARIO_ROBOT' };
const serverResult = object
  ? { kind: kind.toUpperCase(), roles: [{ label: 'Перевозка', works: [row] }] }
  : { roles: [{ label: 'Водитель погрузчика', selected_position_id: 'SCENARIO_ROBOT', candidates: [row] }] };
const originalFetch = window.fetch.bind(window);
window.fetch = (url, options) => String(url).includes('/api/v2/') && options?.method === 'POST'
  ? Promise.resolve(new Response(JSON.stringify(serverResult), { status: 200,
    headers: { 'Content-Type': 'application/json' } }))
  : originalFetch(url, options);

export function VisualCheck() {
  const [overlay, setOverlay] = useState(null);
  const [pose, setPose] = useState(null);
  const onPlayback = useCallback((next) => setPose(next), []);
  if (!fixture) return <p>Unknown scene</p>;
  return <main style={{ maxWidth: 1440, margin: 'auto' }}>
    <h1>Визуальная проверка playback · {kind}</h1>
    <p>Ответ API подменён синтетическим результатом серверного A*. Опубликованный каталог и гостевая воронка здесь не проверяются.</p>
    <output id="recovery-pose" data-x={pose?.[0]} data-y={pose?.[1]}>{pose ? pose.map((v) => v.toFixed(2)).join(', ') : 'Не запущено'}</output>
    <SceneModelPreview kind={kind} overlay={overlay} pose={pose} />
    <SceneSimulationControls kind={kind} roleInput={input} report={serverResult}
      onChanged={() => { setOverlay(null); setPose(null); }}
      onPlayback={onPlayback}
      onSimulated={(_, __, next) => setOverlay(next)} />
  </main>;
}
createRoot(document.getElementById('root')).render(<VisualCheck />);
