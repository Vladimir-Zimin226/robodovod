import { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import SceneModelPreview from '../../src/components/SceneModelPreview.jsx';
import SceneSimulationControls from '../../src/components/SceneSimulationControls.jsx';
import paths from './paths.json';
import '../../src/index.css';

const kind = new URLSearchParams(location.search).get('kind') || 'warehouse';
const realApi = new URLSearchParams(location.search).get('api') === 'real';
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
if (!realApi) window.fetch = (url, options) => String(url).includes('/api/v2/') && options?.method === 'POST'
  ? Promise.resolve(new Response(JSON.stringify(String(url).includes('/route-preview')
    ? { simulation: fixture.result, catalog_robot_confirmed: false,
      economics_confirmed: false } : serverResult), { status: 200,
    headers: { 'Content-Type': 'application/json' } }))
  : originalFetch(url, options);

export function VisualCheck() {
  const [overlay, setOverlay] = useState(null);
  const [pose, setPose] = useState(null);
  const [realInput, setRealInput] = useState(null);
  const [realError, setRealError] = useState('');
  useEffect(() => {
    if (!realApi) return;
    const path = object ? `/api/v2/object-roles/${kind.toUpperCase()}/template`
      : '/api/v2/warehouse-roles/template';
    fetch(path).then((response) => {
      if (!response.ok) throw new Error(`Шаблон работы: HTTP ${response.status}`);
      return response.json();
    }).then((template) => {
      if (object) {
        const process = kind === 'airport' ? 'airport_baggage' : 'clinic_medicines';
        const role = template.roles.find((item) => item.works.some((work) => work.process_code === process));
        const selectedWork = role.works.find((work) => work.process_code === process);
        const roleKeys = ['role_code', 'headcount', 'monthly_employer_cost_rub', 'salary_basis',
          'headcount_source', 'salary_source', 'realizable_labor_share'];
        const workKeys = ['process_code', 'evidence_ref', 'technical_task', 'daily_volume',
          'manual_units_per_person_shift', 'unit', 'allocation_fraction', 'robotizable_share',
          'robot_units_per_hour', 'scenario_purchase_price_rub', 'scenario_raas_monthly_rub',
          'raas_mode', 'raas_percent_monthly', 'rate_source', 'price_source', 'raas_source',
          'basis', 'residual_operations', 'calculation_status', 'safety_conditions', 'task_payload_kg'];
        const selectedRole = Object.fromEntries(roleKeys.map((key) => [key, role[key]]));
        selectedRole.works = [{ ...Object.fromEntries(workKeys.map((key) => [key, selectedWork[key]])),
          selected_position_id: 'SCENARIO_TYPE' }];
        setRealInput({ kind: kind.toUpperCase(), general: template.general, roles: [selectedRole] });
      } else {
        const role = template.roles.find((item) => item.role_code === 'forklift_driver');
        const keys = ['role_code', 'headcount', 'monthly_employer_cost_rub', 'daily_volume',
          'manual_units_per_person_shift', 'robotizable_share', 'source', 'basis'];
        setRealInput({ general: template.general, roles: [Object.fromEntries(keys.map((key) => [key, role[key]]))] });
      }
    }).catch((error) => setRealError(error.message));
  }, []);
  const onPlayback = useCallback((next) => setPose(next), []);
  if (!fixture) return <p>Unknown scene</p>;
  const realReport = object
    ? { kind: kind.toUpperCase(), roles: [{ label: kind === 'airport' ? 'Багаж' : 'Доставка',
      works: [{ selected_position_id: 'SCENARIO_TYPE' }] }] }
    : { roles: [{ label: 'Водитель погрузчика', selected_position_id: null, candidates: [] }] };
  return <main style={{ maxWidth: 1440, margin: 'auto' }}>
    <h1>Визуальная проверка playback · {kind}</h1>
    <p>{realApi ? 'Ответ получен от локального FastAPI route-preview. Каталожная модель и экономика этим маршрутом не подтверждаются; опубликованный каталог и гостевая воронка здесь не проверяются.'
      : 'Ответ API подменён синтетическим результатом серверного A*. Опубликованный каталог и гостевая воронка здесь не проверяются.'}</p>
    <output id="recovery-pose" data-x={pose?.[0]} data-y={pose?.[1]}>{pose ? pose.map((v) => v.toFixed(2)).join(', ') : 'Не запущено'}</output>
    <SceneModelPreview kind={kind} overlay={overlay} pose={pose} />
    {realError && <p role="alert">{realError}</p>}
    {(!realApi || realInput) && <SceneSimulationControls kind={kind} roleInput={realApi ? realInput : input}
      report={realApi ? realReport : serverResult}
      onChanged={() => { setOverlay(null); setPose(null); }}
      onPlayback={onPlayback}
      onScenario={setOverlay}
      onSimulated={(_, __, next) => setOverlay(next)} />}
  </main>;
}
createRoot(document.getElementById('root')).render(<VisualCheck />);
