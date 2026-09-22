import { useEffect, useMemo, useRef, useState } from 'react';
import {
  createDraft,
  createNormalizationClient,
  confirmRoleAssumption,
  setRoleActive,
  updateProcess,
  updateRole,
  validateDraft,
} from '../processRoleIntakeV2';

const API = import.meta.env.VITE_API_URL || '';

const ROLE_LABELS = {
  forklift_driver: 'Оператор погрузчика', loader: 'Грузчик', storekeeper: 'Кладовщик', picker: 'Комплектовщик',
  sorter: 'Сортировщик', packer: 'Упаковщик', cleaner: 'Уборщик', inventory_worker: 'Сотрудник инвентаризации',
  baggage_handler: 'Обработчик багажа', trolley_operator: 'Оператор тележек', special_equipment_driver: 'Водитель спецтехники',
  terminal_cleaner: 'Уборщик терминала', perron_cleaner: 'Уборщик перрона', runway_inspector: 'Инспектор ВПП', security_guard: 'Сотрудник безопасности',
  passenger_assistant: 'Ассистент пассажиров', courier: 'Курьер', ramp_worker: 'Работник перрона', ground_support_worker: 'Наземное обслуживание',
  catering_worker: 'Работник пищеблока', laundry_worker: 'Работник прачечной', sanitary: 'Санитар', porter: 'Транспортировщик', lab_assistant: 'Лаборант',
  sterile_supply_worker: 'Сотрудник ЦСО', consumable_worker: 'Сотрудник снабжения', lab_result_courier: 'Курьер результатов',
};

const statusFor = (process, issues, response) => {
  if (!process.active) return ['Неактивен', 'text-slate-400'];
  const serverRefs = [
    ...(response?.errors || []).flatMap((item) => item.field_refs || [item.field]),
    ...(response?.required_inputs || []),
  ].filter(Boolean);
  if (serverRefs.some((ref) => ref.includes(process.blockId))) return ['Сервер: нужны данные', 'text-amber-700'];
  if (response?.normalized_processes?.some((item) => item.process_id === process.processId)) return ['Сервер: нормализован', 'text-green-700'];
  if (issues.some((item) => item.ref.startsWith(process.code) && item.severity === 'BLOCKER')) return ['Нужны данны', 'text-red-600'];
  if (issues.some((item) => item.ref === process.code && item.code === 'NO_FOT_BENEFIT')) return ['Без ФОТ-эффекта', 'text-amber-600'];
  return ['Готов к нормализации', 'text-green-600'];
};

export default function ProcessRoleIntakeV2({ objectType, onNormalized }) {
  const [draft, setDraft] = useState(() => createDraft(objectType));
  const [expanded, setExpanded] = useState(null);
  const [result, setResult] = useState(null);
  const [state, setState] = useState('');
  const [error, setError] = useState('');
  const latestRevision = useRef(draft.inputRevision);
  const normalizationClient = useRef(null);
  useEffect(() => {
    latestRevision.current = draft.inputRevision;
  }, [draft.inputRevision]);
  useEffect(() => {
    normalizationClient.current = createNormalizationClient(
      (url, options) => fetch(`${API}${url}`, options),
      '/api/v2/calculation-intake/normalize',
      () => latestRevision.current,
    );
  }, []);

  const issues = useMemo(() => validateDraft(draft), [draft]);
  const blockers = issues.filter((item) => item.severity === 'BLOCKER');
  const activeCount = draft.processes.filter((item) => item.active).length;

  const normalize = async () => {
    if (blockers.length || activeCount === 0) return;
    setState('loading');
    setError('');
    try {
      const normalized = await normalizationClient.current(draft);
      setResult(normalized);
      onNormalized?.(normalized);
      setState('ready');
    } catch (requestError) {
      if (requestError.code === 'STALE_INTAKE_RESPONSE') return;
      setError(requestError.message || 'Не удалось проверить ввод');
      setState('');
    }
  };

  return (
    <aside className="w-[480px] border-l bg-white p-4 overflow-auto" aria-label="Процессы и роли v2">
      <header className="mb-3">
        <div className="flex justify-between gap-3 items-start">
          <div><h2 className="font-semibold">Процессы и роли</h2><p className="text-xs text-slate-500">Черновик v2 · {draft.inputRevision}</p></div>
          <span className="text-[10px] rounded bg-blue-50 text-blue-700 px-2 py-1">{draft.schemaVersion}</span>
        </div>
        <p className="text-xs text-slate-500 mt-2">Вводите исходные значения. Единицы и производные величины проверяет сервер.</p>
      </header>

      <div className="space-y-2">
        {draft.processes.map((process) => {
          const open = expanded === process.code;
          const [status, statusClass] = statusFor(process, issues, result?.response);
          return (
            <section key={process.blockId} className={`border rounded-lg ${process.active ? 'border-blue-300' : 'border-slate-200'}`}>
              <div className="flex items-center gap-2 px-3 py-2">
                <input id={`active-${process.code}`} type="checkbox" checked={process.active} onChange={(event) => setDraft((current) => updateProcess(current, process.code, { active: event.target.checked, activationSource: 'USER' }))} />
                <label htmlFor={`active-${process.code}`} className="flex-1 text-sm font-medium">{process.label}</label>
                <button type="button" aria-expanded={open} aria-controls={`panel-${process.code}`} onClick={() => setExpanded(open ? null : process.code)} className="text-xs text-blue-700">{open ? 'Свернуть' : 'Открыть'}</button>
              </div>
              <div className="px-3 pb-2 flex justify-between text-[10px]"><span>{process.scope}</span><span className={statusClass}>{status}</span></div>
              {open && <div id={`panel-${process.code}`} className="border-t bg-slate-50 p-3 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <NumberField label={`Объём, ${process.unit}`} value={process.demand} onChange={(value) => setDraft((current) => updateProcess(current, process.code, { demand: value }))} />
                  <NumberField label="Смен/сут" value={process.shifts} onChange={(value) => setDraft((current) => updateProcess(current, process.code, { shifts: value }))} />
                  <NumberField label="Часов/смена" value={process.hours} onChange={(value) => setDraft((current) => updateProcess(current, process.code, { hours: value }))} />
                  <NumberField label="Дней/год" value={process.days} onChange={(value) => setDraft((current) => updateProcess(current, process.code, { days: value }))} />
                  {['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) && <NumberField label="Плечо, m" value={process.distance} onChange={(value) => setDraft((current) => updateProcess(current, process.code, { distance: value }))} />}
                  {['BOX', 'CASE', 'KILOGRAM', 'SAMPLE', 'SET', 'BIN', 'ITEM', 'PORTION'].includes(process.quantityKind) && <NumberField label="Единиц/рейс" value={process.batch} onChange={(value) => setDraft((current) => updateProcess(current, process.code, { batch: value }))} />}
                </div>
                <fieldset><legend className="text-xs font-semibold">Роли</legend>
                  {process.roles.length === 0 ? <p className="text-xs text-slate-500 mt-1">Роль не требуется: ФОТ-эффект не рассчитывается.</p> : process.roles.map((roleCode) => {
                    const role = draft.roles.find((item) => item.roleCode === roleCode && item.processIds.includes(process.processId));
                    return <div key={roleCode} className="mt-2 border rounded bg-white p-2">
                      <label className="flex gap-2 text-xs"><input type="checkbox" checked={Boolean(role)} onChange={(event) => setDraft((current) => setRoleActive(current, process.code, roleCode, event.target.checked))} />{ROLE_LABELS[roleCode] || roleCode}</label>
                      {role && <div className="grid grid-cols-2 gap-2 mt-2">
                        <NumberField label="Численность, person" value={role.headcount} onChange={(value) => setDraft((current) => updateRole(current, role.roleId, { headcount: value }))} />
                        <NumberField label="Зарплата gross, RUB/person/month" value={role.salary} onChange={(value) => setDraft((current) => updateRole(current, role.roleId, { salary: value, salarySource: 'USER' }))} />
                        {role.salarySource === 'ASSUMPTION' && !role.salaryConfirmed && <label className="col-span-2 text-[10px] text-amber-700"><input type="checkbox" className="mr-1" onChange={(event) => event.target.checked && setDraft((current) => confirmRoleAssumption(current, role.roleId))} />Подтверждаю это допущение для revision</label>}
                        {!role.salary && <p className="col-span-2 text-[10px] text-amber-700">Без monthly gross salary техническая проверка возможна, а labour/finance останутся incomplete.</p>}
                      </div>}
                    </div>;
                  })}
                </fieldset>
              </div>}
            </section>
          );
        })}
      </div>

      <div className="mt-3 text-xs" aria-live="polite">
        {blockers.length > 0 && <p className="text-red-600">Исправьте обязательные поля: {blockers.length}.</p>}
        {issues.some((item) => item.code === 'SALARY_REQUIRED') && <p className="text-amber-700">Для расчёта ФОТ нужна зарплата каждой активной роли.</p>}
        {error && <p className="text-red-600">{error}</p>}
        {result && <NormalizationTrace result={result} />}
      </div>
      <button type="button" disabled={state === 'loading' || activeCount === 0 || blockers.length > 0} onClick={normalize} className="w-full rounded-xl py-3 mt-3 text-sm font-semibold bg-blue-600 text-white disabled:bg-slate-200 disabled:text-slate-400">
        {state === 'loading' ? 'Проверяем…' : 'Проверить ввод v2'}
      </button>
    </aside>
  );
}

function NumberField({ label, value, onChange }) {
  return <label className="text-[11px] text-slate-600">{label}<input type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} className="w-full border rounded px-2 py-1 text-sm" /></label>;
}

function NormalizationTrace({ result }) {
  const response = result.response;
  return <details className="mt-2 border rounded p-2"><summary className="cursor-pointer font-semibold">Server normalization · {response.valid ? 'валидно' : 'нужны данные'}</summary>
    <p>Revision: {response.input_revision}</p>
    {response.required_inputs?.map((field) => <div key={field} className="text-amber-700">Нужно: {field}</div>)}
    {response.conversions?.map((node) => <div key={node.node_id} className="mt-1"><code>{node.field}</code>: raw {node.raw_value} {node.raw_unit} → normalized {node.normalized_value} {node.normalized_unit} <span className="text-slate-400">({node.provenance.source})</span></div>)}
  </details>;
}
