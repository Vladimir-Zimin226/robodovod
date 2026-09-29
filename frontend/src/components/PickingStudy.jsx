import { useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const fields = [
  ['demand_per_day', 'Операций отбора в сутки'], ['hours_per_shift', 'Часов в смене'],
  ['shifts_per_day', 'Смен в сутки'], ['robot_picks_per_hour', 'Операций робота в час'],
  ['manual_picks_per_shift', 'Операций сотрудника в смену'],
  ['robotizable_fraction', 'Доля роботизируемой работы, 0–1'],
  ['residual_worker_shifts_per_day', 'Остаточная ручная работа, человеко-смен в сутки'],
];

export default function PickingStudy({ project, process, zone, pickerHeadcount = '' }) {
  const [draft, setDraft] = useState(() => ({ schema_version:'warehouse-picking-study-v2', unit:'PICK', demand_per_day:process?.demand?.normalized_value || '',
    hours_per_shift:process?.schedule?.shift_hours?.normalized_value || '8',
    shifts_per_day:process?.schedule?.shifts_per_day?.normalized_value || '2',
    robot_picks_per_hour:'', manual_picks_per_shift:'', robotizable_fraction:'',
    residual_worker_shifts_per_day:'', residual_rate_source:'SYNTHETIC_TEST',
    residual_operations:'', confirmation:false, horizon_years:5, discount_rate:'0.15',
    robot_rate_source:'SYNTHETIC_TEST', manual_rate_source:'SYNTHETIC_TEST',
  }));
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const set = (key, value) => { setDraft((current) => ({ ...current, [key]:value })); setResult(null); };
  const calculate = async () => {
    setError('');
    try {
      const input = { ...draft, shifts_per_day:Number(draft.shifts_per_day),
        robot_rate_source:draft.robot_picks_per_hour ? draft.robot_rate_source : null,
        manual_rate_source:draft.manual_picks_per_shift ? draft.manual_rate_source : null,
        robot_picks_per_hour:draft.robot_picks_per_hour || null, manual_picks_per_shift:draft.manual_picks_per_shift || null,
        robotizable_fraction:draft.robotizable_fraction || null, residual_operations:draft.residual_operations || null,
        residual_worker_shifts_per_day:draft.residual_worker_shifts_per_day === '' ? null : draft.residual_worker_shifts_per_day,
        residual_rate_source:draft.residual_worker_shifts_per_day === '' ? null : draft.residual_rate_source };
      const response = await fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/picking-study/preview`, {
        method:'POST', credentials:'include', headers:{ 'Content-Type':'application/json','X-CSRF-Token':readCsrfCookie() }, body:JSON.stringify(input),
      });
      if (!response.ok) throw new Error(`Проверка отбора: HTTP ${response.status}`);
      setResult(await response.json());
    } catch (reason) { setError(reason.message); }
  };
  return <details open className="rounded-xl border p-4" aria-label="Исследование комплектации">
    <summary>Отдельная проверка комплектации · исследовательский профиль v2</summary>
    <p>{zone?.label ? `${zone.label}: ` : ''}считаются операции отбора, а не перевозка паллет. Объём и график перенесены из выбранного процесса; производительность робота вводится отдельно и не является паспортом позиции каталога.</p>
    <p>Текущий штат комплектовщиков: {pickerHeadcount || 'неизвестен'}. Эта проверка не переводит потенциально избегаемые человеко-смены в сокращение штата или NPV: нужны график, распределение людей, замеры остаточной работы и коммерческие условия.</p>
    <label>Единица<select value={draft.unit} disabled={Boolean(process)} onChange={(event) => set('unit',event.target.value)}><option value="PICK">Операции отбора</option><option value="ORDER_LINE">Строки заказа</option></select></label>
    <div className="grid gap-2 md:grid-cols-3">{fields.map(([key,label]) => <label key={key}>{label}<input type="number" min="0" step="any" value={draft[key]} onChange={(event) => set(key,event.target.value)} /></label>)}</div>
    <div className="grid gap-2 md:grid-cols-2"><label>Источник выработки робота<select value={draft.robot_rate_source} onChange={(event) => set('robot_rate_source',event.target.value)}><option value="SYNTHETIC_TEST">Проверочное допущение</option><option value="MEASUREMENT">Измерение</option></select></label>
      <label>Источник выработки человека<select value={draft.manual_rate_source} onChange={(event) => set('manual_rate_source',event.target.value)}><option value="SYNTHETIC_TEST">Проверочное допущение</option><option value="MEASUREMENT">Измерение</option></select></label>
      <label>Источник остаточной работы<select value={draft.residual_rate_source} onChange={(event) => set('residual_rate_source',event.target.value)}><option value="SYNTHETIC_TEST">Проверочное допущение</option><option value="MEASUREMENT">Измерение</option></select></label></div>
    <label>Остаточные ручные операции<input type="text" value={draft.residual_operations} onChange={(event) => set('residual_operations',event.target.value)} /></label>
    <label><input type="checkbox" checked={draft.confirmation} onChange={(event) => set('confirmation',event.target.checked)} /> Принимаю синтетический профиль только для проверки арифметики.</label>
    <button type="button" onClick={calculate} disabled={!project?.id}>Проверить без сохранения</button>
    {error && <p role="alert">{error}</p>}
    {result && <div role="status"><p>Парк: {result.recommended_fleet ?? 'не рассчитан'}; покрытие спроса роботами: {result.coverage ?? 'не рассчитано'}; потенциально избегаемые человеко-смены в сутки: {result.potential_avoided_worker_shifts_per_day ?? 'не рассчитано'}.</p><p>Подтверждённой реальной модели нет. Вывод о штатных единицах и проектной экономике недоступен.</p>{result.missing?.length > 0 && <p>Недостаёт: {result.missing.join(', ')}.</p>}</div>}
  </details>;
}
