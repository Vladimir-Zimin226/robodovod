import { useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const fields = [
  ['demand_per_day', 'Операций отбора в сутки'], ['hours_per_shift', 'Часов в смене'],
  ['shifts_per_day', 'Смен в сутки'], ['robot_picks_per_hour', 'Операций робота в час'],
  ['manual_picks_per_shift', 'Операций сотрудника в смену'],
  ['robotizable_fraction', 'Доля роботизируемой работы, 0–1'],
  ['existing_pickers', 'Отборщиков сейчас'], ['annual_gross_per_picker', 'Годовая полная стоимость сотрудника, ₽'],
  ['robot_price_gross', 'Цена робота gross, ₽'], ['annual_robot_opex_gross', 'OPEX робота в год, ₽'],
];

export default function PickingStudy({ project }) {
  const [draft, setDraft] = useState({ unit:'PICK', demand_per_day:'', hours_per_shift:'8', shifts_per_day:'2',
    robot_picks_per_hour:'', manual_picks_per_shift:'', robotizable_fraction:'', existing_pickers:'',
    annual_gross_per_picker:'', robot_price_gross:'', annual_robot_opex_gross:'',
    residual_operations:'', confirmation:false, horizon_years:5, discount_rate:'0.15' });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const set = (key, value) => { setDraft((current) => ({ ...current, [key]:value })); setResult(null); };
  const calculate = async () => {
    setError('');
    try {
      const input = { ...draft, shifts_per_day:Number(draft.shifts_per_day), existing_pickers:draft.existing_pickers === '' ? null : Number(draft.existing_pickers),
        robot_rate_source:draft.robot_picks_per_hour ? 'SYNTHETIC_TEST' : null,
        manual_rate_source:draft.manual_picks_per_shift ? 'MEASUREMENT' : null,
        robot_picks_per_hour:draft.robot_picks_per_hour || null, manual_picks_per_shift:draft.manual_picks_per_shift || null,
        robotizable_fraction:draft.robotizable_fraction || null, residual_operations:draft.residual_operations || null,
        annual_gross_per_picker:draft.annual_gross_per_picker || null, robot_price_gross:draft.robot_price_gross || null,
        annual_robot_opex_gross:draft.annual_robot_opex_gross || null };
      const response = await fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/picking-study/preview`, {
        method:'POST', credentials:'include', headers:{ 'Content-Type':'application/json','X-CSRF-Token':readCsrfCookie() }, body:JSON.stringify(input),
      });
      if (!response.ok) throw new Error(`Проверка отбора: HTTP ${response.status}`);
      setResult(await response.json());
    } catch (reason) { setError(reason.message); }
  };
  return <details className="rounded-xl border p-4" aria-label="Исследование комплектации">
    <summary>Отдельная проверка комплектации · синтетический профиль</summary>
    <p>Считаются операции отбора, а не перевозка паллет. Производительность робота здесь ваше проверочное число, без подтверждённой модели каталога.</p>
    <label>Единица<select value={draft.unit} onChange={(event) => set('unit',event.target.value)}><option value="PICK">Операции отбора</option><option value="ORDER_LINE">Строки заказа</option></select></label>
    <div className="grid gap-2 md:grid-cols-3">{fields.map(([key,label]) => <label key={key}>{label}<input type="number" min="0" step="any" value={draft[key]} onChange={(event) => set(key,event.target.value)} /></label>)}</div>
    <label>Остаточные ручные операции<input type="text" value={draft.residual_operations} onChange={(event) => set('residual_operations',event.target.value)} /></label>
    <label><input type="checkbox" checked={draft.confirmation} onChange={(event) => set('confirmation',event.target.checked)} /> Принимаю синтетический профиль только для проверки арифметики.</label>
    <button type="button" onClick={calculate} disabled={!project?.id}>Проверить без сохранения</button>
    {error && <p role="alert">{error}</p>}
    {result && <div role="status"><p>Парк: {result.recommended_fleet ?? 'не рассчитан'}; покрытие: {result.coverage ?? 'не рассчитано'}; высвобождение: {result.released_people ?? 'не рассчитано'} чел.; проектный NPV: {result.project_npv ?? 'не рассчитан'} ₽.</p><p>Подтверждённой реальной модели нет. Для завершения нужны её паспорт отбора, пригодность и коммерческие условия.</p>{result.missing?.length > 0 && <p>Недостаёт: {result.missing.join(', ')}.</p>}</div>}
  </details>;
}
