import { useEffect, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import { ROLE_WORK_SCENARIO_ROWS } from '../roleWorkScenarioAssumptions';

const API = import.meta.env.VITE_API_URL || '';
const LABELS = { picker: 'Комплектовщик', sorter: 'Сортировщик' };
const TYPICAL = Object.fromEntries(ROLE_WORK_SCENARIO_ROWS.filter((row) => row.process_code === 'warehouse_picking')
  .map((row) => [row.role_code, row]));
const MONEY_FIELDS = [
  ['purchase_robot_price', 'Цена решения за робота, ₽'],
  ['purchase_implementation', 'Доставка, внедрение и интеграция покупки, ₽'],
  ['purchase_annual_opex_per_robot', 'Годовое обслуживание одного купленного робота, ₽'],
  ['raas_monthly_per_robot', 'Аренда одного робота в месяц, ₽'],
  ['raas_customer_capex', 'Инфраструктура заказчика для аренды, ₽'],
  ['raas_customer_annual_opex', 'Годовые расходы заказчика при аренде, ₽'],
  ['shared_site_capex', 'Общие первоначальные вложения площадки, ₽'],
  ['shared_site_annual_opex', 'Общие годовые расходы площадки, ₽'],
  ['purchase_new_staff_annual_cost', 'Новый персонал при покупке, ₽/год'],
  ['raas_new_staff_annual_cost', 'Новый персонал при аренде, ₽/год'],
];

function initialRole(code, staffRoles) {
  const row = TYPICAL[code];
  const source = staffRoles.find((role) => role.roleCode === code);
  return { role_code: code, headcount: source?.headcount || row?.object_role_headcount || '',
    monthly_employer_cost: source?.salary || row?.monthly_amount_rub_per_person || '',
    manual_units_per_shift: row?.manual_units_per_person_shift || '',
    robotizable_fraction: row?.robotizable_fraction || '0',
    residual_extra_shifts_per_day: '0', robot_covers_role: code === 'picker',
    source: 'ASSUMPTION',
    basis: `${row?.work_basis || 'Проверочное допущение для роли'}. Штат и расходы: форма объекта.`, confirmed: false };
}

function initialInput(process, staffRoles) {
  return { schema_version: 'warehouse-picking-project-input-v1',
    process_id: process?.process_id || 'unknown.warehouse_picking',
    unit: 'PICK', unit_basis: 'Одна операция отбора условно равна одной строке заказа; подтвердить для объекта',
    unit_confirmed: false, demand_per_day: process?.demand?.normalized_value || '',
    shifts_per_day: process?.schedule?.shifts_per_day?.normalized_value || 2,
    hours_per_shift: process?.schedule?.shift_hours?.normalized_value || '8',
    days_per_year: process?.schedule?.days_per_year?.normalized_value || 250,
    operation_source: 'ASSUMPTION',
    operation_basis: 'Объём и график перенесены из формы объекта; доступность 0,85 и доля 0,35 — проверочные допущения',
    operation_confirmed: false,
    robot_units_per_hour: '', robot_rate_source: 'ASSUMPTION',
    robot_rate_basis: 'Проверочное допущение, не характеристика позиции каталога',
    robot_rate_confirmed: false, availability_fraction: '0.85',
    robotizable_fraction: '0.35', selected_fleet: '',
    roles: ['picker', 'sorter'].map((code) => initialRole(code, staffRoles)),
    money: { purchase_robot_price: '', purchase_implementation: '',
      purchase_annual_opex_per_robot: '', raas_monthly_per_robot: '',
      raas_customer_capex: '', raas_customer_annual_opex: '',
      shared_site_capex: '', shared_site_annual_opex: '',
      purchase_new_staff_annual_cost: '', raas_new_staff_annual_cost: '',
      horizon_years: 5, discount_rate: '0.15', source: 'ASSUMPTION',
      basis: 'Проверочные финансовые условия, не предложение поставщика', confirmed: false } };
}

function payloadOf(values) {
  return { ...values, shifts_per_day: Number(values.shifts_per_day),
    days_per_year: Number(values.days_per_year),
    robot_units_per_hour: values.robot_units_per_hour || null,
    robot_rate_source: values.robot_units_per_hour ? values.robot_rate_source : null,
    selected_fleet: values.selected_fleet === '' ? null : Number(values.selected_fleet),
    roles: values.roles.map((role) => ({ ...role, headcount: Number(role.headcount),
      monthly_employer_cost: role.monthly_employer_cost || null,
      manual_units_per_shift: role.manual_units_per_shift || null })),
    money: { ...values.money, horizon_years: Number(values.money.horizon_years),
      ...Object.fromEntries(MONEY_FIELDS.map(([key]) => [key, values.money[key] === '' ? null : values.money[key]])) } };
}

const money = (value) => value == null ? 'не рассчитано' : `${Number(value).toLocaleString('ru-RU')} ₽`;

export default function PickingProjectCalculator({ project, process, staffRoles = [] }) {
  const [values, setValues] = useState(() => initialInput(process, staffRoles));
  const [result, setResult] = useState(null);
  const [saved, setSaved] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const base = project?.id ? `${API}/api/v2/projects/${encodeURIComponent(project.id)}/picking-runs` : '';
  const picker = values.roles.find((role) => role.role_code === 'picker');
  const staffedDemand = Number(picker?.headcount) * Number(picker?.manual_units_per_shift);
  useEffect(() => {
    if (!base) return undefined;
    const controller = new AbortController();
    fetch(`${base}?process_id=${encodeURIComponent(process.process_id)}`, { credentials: 'include', signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then((data) => { if (!controller.signal.aborted) setHistory(data.items || []); })
      .catch(() => {});
    return () => controller.abort();
  }, [base, process.process_id]);
  const refreshStaff = () => {
    const present = staffRoles.filter((role) => LABELS[role.roleCode]);
    setValues((current) => ({ ...current, roles: current.roles.map((role) => {
      const source = present.find((item) => item.roleCode === role.role_code);
      return source ? { ...role, headcount: source.headcount,
        monthly_employer_cost: source.salary, source: 'ASSUMPTION',
        basis: 'Численность и расходы перенесены из формы объекта; выработка и доля остаются проектными допущениями',
        confirmed: false } : role;
    }) }));
    setResult(null);
    setMessage(`Обновлены данные ${present.length} ролей из формы объекта. Проверьте и подтвердите каждую роль в сценарии.`);
  };
  const useStaffedDemandAssumption = () => {
    if (!Number.isFinite(staffedDemand) || staffedDemand <= 0) return;
    setValues((current) => ({ ...current, unit: 'ORDER_LINE',
      demand_per_day: String(staffedDemand),
      unit_basis: `Проверочное допущение: ${picker.headcount} комплектовщиков × ${picker.manual_units_per_shift} строк за смену = ${staffedDemand} строк/сутки при одной отработанной смене на человека; это штатная мощность, не измеренный поток.`,
      unit_confirmed: true, operation_source: 'ASSUMPTION', operation_confirmed: false,
      operation_basis: 'Объём по штатной мощности, не измеренный поток; график взят из формы, доступность и доля являются проверочными допущениями' }));
    setResult(null);
    setMessage(`Для сценария принято ${staffedDemand} строк/сутки по штатной мощности. Это допущение; замените реальным потоком при проверке объекта.`);
  };
  const field = (key) => (event) => { setValues((current) => ({ ...current,
    [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
    ...(['unit', 'unit_basis', 'demand_per_day'].includes(key) ? { unit_confirmed: false } : {}),
    ...(['demand_per_day', 'shifts_per_day', 'hours_per_shift', 'days_per_year',
      'availability_fraction', 'robotizable_fraction', 'operation_source', 'operation_basis'].includes(key)
      ? { operation_confirmed: false } : {}),
    ...(['robot_units_per_hour', 'robot_rate_source', 'robot_rate_basis'].includes(key)
      ? { robot_rate_confirmed: false } : {}) })); setResult(null); };
  const roleField = (code, key) => (event) => { setValues((current) => ({ ...current,
    roles: current.roles.map((role) => role.role_code === code
      ? { ...role, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
        confirmed: key === 'confirmed' ? event.target.checked : false }
      : role) })); setResult(null); };
  const moneyField = (key) => (event) => { setValues((current) => ({ ...current,
    money: { ...current.money, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
      confirmed: key === 'confirmed' ? event.target.checked : false } })); setResult(null); };
  const preset = () => {
    setValues((current) => ({ ...current, unit_confirmed: true, operation_confirmed: true,
      robot_units_per_hour: current.robot_units_per_hour || '100',
      robot_rate_source: current.robot_units_per_hour ? current.robot_rate_source : 'ASSUMPTION',
      robot_rate_basis: current.robot_units_per_hour ? current.robot_rate_basis
        : 'Авторское проверочное допущение: 100 операций отбора в час, не паспорт модели',
      robot_rate_confirmed: true, roles: current.roles.map((role) => ({ ...role, confirmed: true })),
      money: { ...current.money,
        purchase_robot_price: current.money.purchase_robot_price || '2000000',
        purchase_implementation: current.money.purchase_implementation || '5000000',
        purchase_annual_opex_per_robot: current.money.purchase_annual_opex_per_robot || '250000',
        raas_monthly_per_robot: current.money.raas_monthly_per_robot || '200000',
        raas_customer_capex: current.money.raas_customer_capex || '1000000',
        raas_customer_annual_opex: current.money.raas_customer_annual_opex || '100000',
        shared_site_capex: current.money.shared_site_capex || '0',
        shared_site_annual_opex: current.money.shared_site_annual_opex || '0',
        purchase_new_staff_annual_cost: current.money.purchase_new_staff_annual_cost || '0',
        raas_new_staff_annual_cost: current.money.raas_new_staff_annual_cost || '0',
        confirmed: true } }));
    setResult(null); setMessage('Проверочные числа приняты как допущения. Проверьте их перед сохранением; реальная модель каталога этим не подтверждена.');
  };
  const calculate = async (save) => {
    if (!base) { setError('Выберите проект для расчёта комплектации.'); return; }
    setBusy(true); setError(''); setMessage('');
    let responseStatus = null;
    try {
      const response = await fetch(save ? base : `${base}/preview`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(save ? { input: payloadOf(values), parent_run_id: saved?.id || null } : payloadOf(values)),
      });
      responseStatus = response.status;
      const body = await response.json();
      if (!response.ok) throw new Error(Array.isArray(body.detail)
        ? body.detail.map((issue) => `${issue.loc?.slice(-1)[0] || 'поле'}: ${issue.msg}`).join('; ')
        : typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
      console.info('ROBODOVOD_UI_ACTION', { action: save ? 'SAVE_PICKING_RUN' : 'PREVIEW_PICKING_RUN',
        status: 'SUCCEEDED', reason_code: body.status || body.result_snapshot?.status || 'OK',
        run_id: save ? body.id : null });
      if (save) {
        setSaved(body); setResult(body.result_snapshot);
        setHistory((current) => [{ id: body.id, status: body.status, created_at: body.created_at }, ...current]);
        setMessage('Новый расчёт комплектации сохранён. PDF, CSV и ZIP читают этот снимок.');
      } else { setResult(body); setMessage('Предварительный результат не сохранён.'); }
    } catch (reason) {
      console.info('ROBODOVOD_UI_ACTION', { action: save ? 'SAVE_PICKING_RUN' : 'PREVIEW_PICKING_RUN',
        status: 'FAILED', reason_code: responseStatus ? `HTTP_${responseStatus}` : 'NETWORK_ERROR', run_id: null });
      setError(String(reason.message));
    }
    finally { setBusy(false); }
  };
  const openRun = async (id) => {
    setBusy(true); setError('');
    try {
      const response = await fetch(`${base}/${encodeURIComponent(id)}`, { credentials: 'include' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const body = await response.json();
      setSaved(body); setResult(body.result_snapshot); setValues(body.input_snapshot);
      setMessage('Сохранённый расчёт открыт. Измените числа и сохраните новую версию.');
    } catch (reason) { setError(String(reason.message)); }
    finally { setBusy(false); }
  };
  const replay = async () => {
    if (!saved) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${base}/${encodeURIComponent(saved.id)}/replay`, {
        method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': readCsrfCookie() },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setMessage('Повторный расчёт совпал с сохранённым результатом.');
    } catch (reason) { setError(String(reason.message)); }
    finally { setBusy(false); }
  };
  return <section className="rounded-xl border border-lime-500 bg-white p-4 text-slate-900" aria-label="Сохранённый расчёт комплектации">
    <h4 className="text-lg font-semibold">Рассчитать комплектацию как отдельную работу</h4>
    <p className="text-sm">Этот профиль считает отбор товара, комплектовщика и сортировщика отдельно от перевозки паллет. Проверочная выработка — допущение; закупочная рекомендация не формируется.</p>
    {!project && <p className="mt-2 rounded border border-amber-400 p-2 text-sm" role="status">Выберите проект выше. Без проекта предварительную проверку и новый run сохранить нельзя.</p>}
    <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={refreshStaff} className="secondary-action">Подтянуть штат и расходы из формы объекта</button>
      <button type="button" onClick={preset} className="secondary-action">Принять проверочные допущения для отдельного сценария</button></div>
    {Number.isFinite(staffedDemand) && staffedDemand > Number(values.demand_per_day) * 2 && <div className="mt-2 rounded border border-amber-400 p-2 text-sm">
      <p>Проверьте объём: указано {values.demand_per_day || 'неизвестно'} {values.unit}/сутки, а штатная мощность комплектовщиков по допущению составляет {staffedDemand} строк/сутки. При таком объёме расчёт может показать нулевое высвобождение, даже если робот покрывает часть работы.</p>
      <button type="button" className="secondary-action mt-2" onClick={useStaffedDemandAssumption}>Принять сценарный объём {staffedDemand} строк/сутки по штату</button>
    </div>}
    <p className="mt-2 text-sm">Этот результат относится к процессу {values.process_id}. Если одни сотрудники участвуют в нескольких работах, подтвердите распределение времени до сложения отдельных сценариев.</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <label>Единица работы<select value={values.unit} onChange={field('unit')} className="block w-full border p-2"><option value="PICK">Операция отбора (PICK)</option><option value="ORDER_LINE">Строка заказа</option></select></label>
      <label>Операций в сутки<input type="number" min="1" value={values.demand_per_day} onChange={field('demand_per_day')} className="block w-full border p-2" /></label>
      <label>Рабочих дней в году<input type="number" min="1" max="366" value={values.days_per_year} onChange={field('days_per_year')} className="block w-full border p-2" /></label>
      <label>Смен в сутки<input type="number" min="1" max="3" value={values.shifts_per_day} onChange={field('shifts_per_day')} className="block w-full border p-2" /></label>
      <label>Часов в смене<input type="number" min="0" step="any" value={values.hours_per_shift} onChange={field('hours_per_shift')} className="block w-full border p-2" /></label>
      <label>Выработка решения, единиц в час<input type="number" min="0" step="any" value={values.robot_units_per_hour} onChange={field('robot_units_per_hour')} className="block w-full border p-2" /></label>
      <label>Доступность решения, 0–1<input type="number" min="0" max="1" step="any" value={values.availability_fraction} onChange={field('availability_fraction')} className="block w-full border p-2" /></label>
      <label>Доля спроса для робота, 0–1<input type="number" min="0" max="1" step="any" value={values.robotizable_fraction} onChange={field('robotizable_fraction')} className="block w-full border p-2" /></label>
      <label>Выбранный парк, пусто = расчётный<input type="number" min="0" value={values.selected_fleet} onChange={field('selected_fleet')} className="block w-full border p-2" /></label>
    </div>
    <label className="mt-2 block">Основание единицы и связь со строкой заказа<input value={values.unit_basis} onChange={field('unit_basis')} className="block w-full border p-2" /></label>
    <label className="mt-2 flex gap-2"><input type="checkbox" checked={values.unit_confirmed} onChange={field('unit_confirmed')} />Подтверждаю единицу спроса для этого сценария</label>
    <label className="mt-2 block">Источник объёма, графика, доступности и доли<select value={values.operation_source} onChange={field('operation_source')} className="block w-full border p-2"><option value="ASSUMPTION">Проектное допущение</option><option value="USER">Данные объекта</option></select></label>
    <label className="mt-2 block">Основание операционных входов<input value={values.operation_basis} onChange={field('operation_basis')} className="block w-full border p-2" /></label>
    <label className="mt-2 flex gap-2"><input type="checkbox" checked={values.operation_confirmed} onChange={field('operation_confirmed')} />Принимаю объём, график, доступность и долю для сценария</label>
    <label className="mt-2 block">Источник выработки<select value={values.robot_rate_source} onChange={field('robot_rate_source')} className="block w-full border p-2"><option value="ASSUMPTION">Проектное допущение</option><option value="MEASUREMENT">Замер</option></select></label>
    <label className="mt-2 block">Основание выработки<input value={values.robot_rate_basis} onChange={field('robot_rate_basis')} className="block w-full border p-2" /></label>
    <label className="mt-2 flex gap-2"><input type="checkbox" checked={values.robot_rate_confirmed} onChange={field('robot_rate_confirmed')} />Принимаю выработку для проверочного расчёта; это не паспорт модели</label>
    <h5 className="mt-4 font-semibold">Роли и остаточная работа</h5>
    <p className="text-sm">Остаточные человеко-смены ниже относятся только к работе вне указанного объёма отбора. Работа, оставшаяся в объёме после робота, уже учитывается формулой.</p>
    {values.roles.map((role) => <fieldset key={role.role_code} className="mt-2 rounded border p-3"><legend>{LABELS[role.role_code]}</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {[['headcount', 'Штат, чел.'], ['monthly_employer_cost', 'Расходы компании, ₽/мес.'],
          ['manual_units_per_shift', 'Выработка человека за смену'],
          ['robotizable_fraction', 'Заменяемая доля, 0–1'],
          ['residual_extra_shifts_per_day', 'Дополнительная остаточная работа, смен/сутки']].map(([key, label]) =>
          <label key={key}>{label}<input type="number" min="0" step="any" value={role[key]} onChange={roleField(role.role_code, key)} className="block w-full border p-2" /></label>)}
      </div>
      <label className="mt-2 flex gap-2"><input type="checkbox" checked={role.robot_covers_role} onChange={roleField(role.role_code, 'robot_covers_role')} />Решение выполняет заменяемые задачи этой роли</label>
      <label className="mt-2 block">Основание роли<input value={role.basis} onChange={roleField(role.role_code, 'basis')} className="block w-full border p-2" /></label>
      <label className="mt-2 flex gap-2"><input type="checkbox" checked={role.confirmed} onChange={roleField(role.role_code, 'confirmed')} />Подтверждаю данные роли как {role.source === 'ASSUMPTION' ? 'проектное допущение' : 'данные объекта'}</label>
    </fieldset>)}
    <details className="mt-4 rounded border p-3"><summary className="font-semibold">Покупка и аренда: денежные условия</summary>
      <p className="text-sm">Пусто означает «неизвестно». Ноль — отдельное принятое допущение. Общие расходы площадки относятся к обеим схемам.</p>
      <div className="grid gap-2 sm:grid-cols-2">{MONEY_FIELDS.map(([key, label]) => <label key={key}>{label}<input type="number" min="0" step="any" value={values.money[key]} onChange={moneyField(key)} className="block w-full border p-2" /></label>)}</div>
      <label>Горизонт, лет<input type="number" min="1" max="15" value={values.money.horizon_years} onChange={moneyField('horizon_years')} className="block w-full border p-2" /></label>
      <label>Дисконтирование, 0–1<input type="number" min="0" max="1" step="any" value={values.money.discount_rate} onChange={moneyField('discount_rate')} className="block w-full border p-2" /></label>
      <label className="block">Основание денежных условий<input value={values.money.basis || ''} onChange={moneyField('basis')} className="block w-full border p-2" /></label>
      <label className="flex gap-2"><input type="checkbox" checked={values.money.confirmed} onChange={moneyField('confirmed')} />Принимаю эти денежные условия для сценарной оценки</label>
    </details>
    <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={!project || busy} className="secondary-action" onClick={() => calculate(false)}>Проверить без сохранения</button>
      <button type="button" disabled={!project || busy} className="primary-action" onClick={() => calculate(true)}>{saved ? 'Сохранить новую версию' : 'Рассчитать и сохранить комплектацию'}</button></div>
    {error && <p role="alert" className="mt-3 text-red-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-blue-800">{message}</p>}
    {result && <div className="mt-4 rounded border border-teal-400 p-3" aria-label="Результат комплектации">
      <strong>Статус: {result.status === 'COMPLETE' ? 'рассчитано' : 'частично'}</strong>
      <p>Парк: {result.capacity.selected_fleet ?? 'не рассчитан'}; покрыто {result.capacity.covered_units_per_day ?? 'не рассчитано'} {result.unit}/сутки.</p>
      {result.labour.roles.map((role) => <p key={role.role_code}>{LABELS[role.role_code]}: штат {role.headcount}, высвобождено {role.released_people ?? 'не рассчитано'}, осталось {role.remaining_people ?? 'не рассчитано'}; {role.source === 'ASSUMPTION' ? 'проектное допущение' : 'данные объекта'}.</p>)}
      {Object.entries(result.financial).map(([name, finance]) => <p key={name}>{name === 'purchase' ? 'Покупка' : 'Аренда'}: NPV {money(finance.npv_rub)}, TCO {money(finance.tco_rub)}, ROI {finance.roi_pct ?? 'не определён'}{finance.roi_pct == null ? '' : ' %'}.</p>)}
      {result.missing.length > 0 && <p className="text-amber-800">Нужно уточнить: {result.missing.join(', ')}.</p>}
      <p>Закупочная рекомендация недоступна: выработка не привязана к проверенной модели каталога.</p>
    </div>}
    {saved && <div className="mt-3 flex flex-wrap gap-3 text-sm"><button type="button" className="secondary-action" disabled={busy} onClick={replay}>Проверить повторный расчёт</button>
      {['pdf', 'csv'].map((kind) => <a key={kind} className="underline" href={`${base}/${encodeURIComponent(saved.id)}/report.${kind}`}>Скачать {kind.toUpperCase()}</a>)}
      <a className="underline" href={`${base}/${encodeURIComponent(saved.id)}/archive.zip`}>Скачать ZIP</a></div>}
    {history.length > 0 && <details className="mt-4"><summary>Сохранённые версии комплектации · {history.length}</summary>
      {history.map((run) => <button key={run.id} type="button" className="mt-2 block underline" onClick={() => openRun(run.id)}>{new Date(run.created_at).toLocaleString('ru-RU')} · {run.status}</button>)}
    </details>}
  </section>;
}
