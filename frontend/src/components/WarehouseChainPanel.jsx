import { useEffect, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const statusText = {
  CALCULABLE: 'Можно рассчитать парк', COMPARE_ONLY: 'Только сравнение характеристик',
  RESEARCH: 'Исследовательская разработка', INSUFFICIENT_DATA: 'Недостаточно данных',
  CATALOG_UNAVAILABLE: 'Каталог недоступен',
};
const roleText = {
  forklift_driver: 'Водитель погрузчика', picker: 'Комплектовщик', sorter: 'Сортировщик',
  packaging_line_operator: 'Оператор упаковочной линии', packer: 'Укладчик паллет',
};
const physicsLabels = {
  picks_per_hour: 'Захватов в час', max_item_mass_kg: 'Макс. масса штуки, кг',
  max_width_mm: 'Макс. ширина, мм', max_height_mm: 'Макс. высота, мм', gripper: 'Тип захвата',
  reach_mm: 'Досягаемость, мм', cycle_seconds: 'Цикл, сек.', availability: 'Доступность, доля 0–1',
  rack_compatibility: 'Совместимость со стеллажом', tote_feed: 'Подача тары',
};
const sourceText = { UNKNOWN: 'Источник неизвестен', USER: 'Слова пользователя', FILE: 'Файл проекта',
  EXPERT_ASSUMPTION: 'Явное допущение', VENDOR: 'Паспорт поставщика' };

function input(value, onChange, label, width = 'w-24') {
  return <input aria-label={label} className={`${width} rounded border p-1`} value={value ?? ''} onChange={(event) => onChange(event.target.value)} />;
}

export default function WarehouseChainPanel({ project, suggestedTransport = null }) {
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(null);
  const [transportRun, setTransportRun] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [newResource, setNewResource] = useState({ resource_id: '', kind: 'EQUIPMENT', amount: '', unit: 'ед.' });
  useEffect(() => {
    if (!project?.id) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/warehouse-chain/projects/${encodeURIComponent(project.id)}`, { credentials: 'include', signal: controller.signal })
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((data) => { setRecord(data); setDraft(structuredClone(data.chain)); })
      .catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    fetch(`${API}/api/projects/${encodeURIComponent(project.id)}/analysis-runs`, { credentials: 'include', signal: controller.signal })
      .then((r) => r.ok ? r.json() : { items: [] })
      .then(async (data) => {
        const capacityRuns = (data.items || []).filter((run) => run.run_kind === 'CAPACITY_ANALYSIS' && run.status === 'SUCCEEDED');
        for (const run of capacityRuns) {
          const response = await fetch(`${API}/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(run.id)}`, { credentials: 'include', signal: controller.signal });
          if (!response.ok) continue;
          const details = await response.json();
          if (details.input_snapshot?.process?.process_code === 'warehouse_receiving_shipping') { setTransportRun(details.id); break; }
        }
      }).catch(() => {});
    return () => controller.abort();
  }, [project?.id]);

  const flow = (code, patch) => setDraft((current) => ({ ...current,
    flows: current.flows.map((item) => item.code === code ? { ...item, ...patch } : item) }));
  const resource = (id, patch) => setDraft((current) => ({ ...current,
    resources: current.resources.map((item) => item.resource_id === id ? { ...item, ...patch } : item) }));
  const conversion = (index, patch) => setDraft((current) => ({ ...current,
    conversions: current.conversions.map((item, at) => at === index ? { ...item, ...patch } : item) }));
  const applyTransport = () => {
    if (!suggestedTransport?.demand) return;
    flow('receiving_putaway', {
      value: String(suggestedTransport.demand), source: suggestedTransport.source || 'USER', confirmed: false,
      source_ref: suggestedTransport.source === 'EXPERT_ASSUMPTION' ? 'Типовой сценарий; подтвердите применимость' : null,
      shifts_per_day: suggestedTransport.shifts || null, hours_per_shift: suggestedTransport.hours || null,
      days_per_year: suggestedTransport.days || null, zone: suggestedTransport.zone || 'Основная зона',
    });
    setNotice('Объём перенесён в черновик приёмки без подтверждения. Отгрузка, отбор и упаковка остались отдельными неизвестными потоками.');
  };
  const save = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await fetch(`${API}/api/warehouse-chain/projects/${encodeURIComponent(project.id)}/versions`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ expected_version: record.chain.version, flows: draft.flows, resources: draft.resources, conversions: draft.conversions }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
      setRecord(data); setDraft(structuredClone(data.chain)); setNotice(`Сохранена версия ${data.chain.version}. Расчётные runs не изменены.`);
    } catch (reason) { setError(reason.message || 'Не удалось сохранить цепочку.'); }
    finally { setBusy(false); }
  };

  return <section className="panel space-y-3 p-4 text-sm" aria-label="Складская цепочка и охват">
    <h2 className="text-lg font-semibold">Складская цепочка и охват</h2>
    <p>Перевозка подготовленных паллет — отдельный участок. Отбор строк и штук, передача тары, упаковка и паллетизация имеют собственные потоки и роли. Число строк не превращается в число паллетных рейсов без подтверждённой связи.</p>
    {!project && <p>Выберите проект, чтобы сохранить карту операций. Текущий C11 охватывает только выбранный маршрут перевозки паллет.</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {notice && <p role="status" className="text-emerald-700">{notice}</p>}
    {record && draft && <>
      <p>Схема {draft.schema_version} · версия {draft.version} · каталог {record.capabilities.catalog_version || 'недоступен'}. Общие ресурсы записаны один раз на проект.</p>
      <div className="overflow-x-auto"><table className="min-w-[700px] w-full border-collapse text-left text-xs"><thead><tr>
        <th className="border p-2">Операция и роль</th><th className="border p-2">Поток</th><th className="border p-2">Охват</th><th className="border p-2">Возможность каталога</th>
      </tr></thead><tbody>
        <tr><td className="border p-2">Выбранный маршрут перевозки паллет · водитель погрузчика</td><td className="border p-2">Из сохранённого C11</td>
          <td className="border p-2">{transportRun ? 'Учтено в сохранённом C11' : 'Нет сохранённого C11 для паллет'}</td>
          <td className="border p-2">Независимый расчёт выбранного маршрута</td></tr>
        {record.capabilities.rows.map((item) => {
          const current = draft.flows.find((entry) => entry.code === item.code);
          return <tr key={item.code}><td className="border p-2">{item.label}<br /><span className="text-slate-500">{roleText[item.role_code] || item.role_code}</span></td>
            <td className="border p-2">{current?.confirmed ? `${current.value} ${item.unit}` : current?.value ? `Нужно подтвердить: ${current.value} ${item.unit}` : 'Неизвестен'}</td>
            <td className="border p-2">Не учтено в паллетном C11</td>
            <td className="border p-2"><strong>{statusText[item.status]}</strong><br />{item.reason}<br />Позиции: {item.candidate_count}
              {item.code.startsWith('picking_') && <span className="block">Роборука: {item.solution_families.ROBOT_ARM}; AS-RS/G2P: {item.solution_families.ASRS_G2P}; Voice/Light: {item.solution_families.PICK_ASSIST}; прочее: {item.solution_families.OTHER_PICKING}.</span>}</td></tr>;
        })}</tbody></table></div>
      <details><summary className="cursor-pointer font-semibold">Заполнить и сохранить отдельные потоки</summary>
        {suggestedTransport?.demand && <button type="button" className="secondary-action mt-2" onClick={applyTransport}>Перенести паллетный объём из текущего ввода как неподтверждённый</button>}
        <div className="mt-3 space-y-3">{draft.flows.map((item) => {
          const capability = record.capabilities.rows.find((row) => row.code === item.code);
          return <div key={item.code} className="rounded border p-2"><strong>{capability?.label}</strong> · {item.unit} · {roleText[item.role_code]}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <label>Объём {input(item.value, (value) => flow(item.code, { value: value || null, source: value ? 'USER' : 'UNKNOWN', confirmed: false }), `${item.code}: объём`)}</label>
              <label>Смен {input(item.shifts_per_day, (value) => flow(item.code, { shifts_per_day: value || null }), `${item.code}: смен`, 'w-12')}</label>
              <label>Часов {input(item.hours_per_shift, (value) => flow(item.code, { hours_per_shift: value || null }), `${item.code}: часов`, 'w-12')}</label>
              <label>Дней {input(item.days_per_year, (value) => flow(item.code, { days_per_year: value || null }), `${item.code}: дней`, 'w-14')}</label>
              <label>Зона {input(item.zone, (value) => flow(item.code, { zone: value }), `${item.code}: зона`, 'w-32')}</label>
              <label>Источник <select className="rounded border p-1" value={item.source} onChange={(event) => flow(item.code, { source: event.target.value, confirmed: false })}>
                {['UNKNOWN', 'USER', 'FILE', 'EXPERT_ASSUMPTION'].map((source) => <option key={source} value={source}>{sourceText[source]}</option>)}</select></label>
              {['FILE', 'EXPERT_ASSUMPTION'].includes(item.source) && <label>Ссылка/обоснование {input(item.source_ref, (value) => flow(item.code, { source_ref: value || null, confirmed: false }), `${item.code}: источник`, 'w-40')}</label>}
              <label><input type="checkbox" checked={item.confirmed} disabled={!item.value || item.source === 'UNKNOWN'} onChange={(event) => flow(item.code, { confirmed: event.target.checked })} /> Подтверждено</label>
            </div>
            <div className="mt-2 flex flex-wrap gap-2"><label>Решение <select className="rounded border p-1" value={item.solution} onChange={(event) => flow(item.code, { solution: event.target.value, position_id: null })}>
              <option value="MANUAL">Ручная операция</option><option value="UNASSESSED">Не выбрано</option><option value="CATALOG">Позиция каталога</option></select></label>
              {item.solution === 'CATALOG' && <label>Позиция <select className="rounded border p-1" value={item.position_id || ''} onChange={(event) => flow(item.code, { position_id: event.target.value || null })}>
                <option value="">Выберите</option>{capability?.candidates.map((candidate) => <option key={candidate.position_id} value={candidate.position_id}>{candidate.name} · {candidate.maturity_status === 'RND' ? 'исследовательская разработка' : candidate.calculation_ready ? `расчётный профиль ${candidate.calculation_profile || ''}` : candidate.maturity_status || 'только сведения'}</option>)}</select></label>}</div>
            {item.code.startsWith('picking_') && <details className="mt-2"><summary>Физический профиль роботизированного отбора</summary>
              <p>AS-RS/G2P подают товар, Voice/Light помогают человеку. Автономный захват требует всех параметров ниже и отдельной формулы; сейчас парк по ним не рассчитывается.</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">{Object.entries(physicsLabels).map(([key, label]) => <label key={key}>{label}
                {input(item.physical_profile[key], (value) => {
                  const physical_profile = { ...item.physical_profile }; if (value) physical_profile[key] = value; else delete physical_profile[key];
                  flow(item.code, { physical_profile, physical_profile_confirmed: false, physical_profile_source: 'USER' });
                }, label, 'ml-2 w-24')}</label>)}</div>
              <label className="mt-2 block">Источник профиля <select className="rounded border p-1" value={item.physical_profile_source}
                onChange={(event) => flow(item.code, { physical_profile_source: event.target.value, physical_profile_confirmed: false })}>
                {['UNKNOWN', 'USER', 'FILE', 'VENDOR'].map((source) => <option key={source} value={source}>{sourceText[source]}</option>)}</select></label>
              {['FILE', 'VENDOR'].includes(item.physical_profile_source) && <label className="mt-2 block">Файл/паспорт и страница
                {input(item.physical_profile_ref, (value) => flow(item.code, { physical_profile_ref: value || null, physical_profile_confirmed: false }), 'Источник физического профиля', 'ml-2 w-52')}</label>}
              <label className="mt-2 block"><input type="checkbox" checked={item.physical_profile_confirmed} disabled={Object.keys(item.physical_profile).length !== 10}
                onChange={(event) => flow(item.code, { physical_profile_confirmed: event.target.checked })} /> Подтверждаю полный физический профиль и источник</label>
            </details>}</div>;
        })}</div>
      </details>
      <details><summary className="cursor-pointer font-semibold">Общие сотрудники и ресурсы — один раз на проект</summary>
        <p>Водитель погрузчика может участвовать в приёмке и отгрузке, но его штат и зарплата хранятся одной записью. Зарплата оператора линии не подставляется упаковщику паллет.</p>
        <p className="mt-2">Текущий ФОТ/год по сохранённым уникальным ролям: <strong>{record.resources.total_status === 'KNOWN' ? `${record.resources.total_annual_gross_fot_rub} ₽` : 'неизвестен: заполните численность и зарплату всех задействованных ролей'}</strong>. Это исходный ФОТ, не экономия от роботов.</p>
        <ul className="mt-2 list-disc pl-5">{record.resources.rows.map((item) => <li key={item.resource_id}>{roleText[item.role_code] || item.resource_id}: {item.kind === 'STAFF' ? item.annual_gross_fot_rub == null ? 'ФОТ неизвестен' : `${item.annual_gross_fot_rub} ₽/год` : item.amount == null ? 'количество неизвестно' : `${item.amount} ${item.unit || ''}`} · операций {item.linked_operations.length}; учтён один раз</li>)}</ul>
        {draft.resources.map((item) => <div key={item.resource_id} className="mt-2 flex flex-wrap gap-2 rounded border p-2">
          <strong>{roleText[item.role_code] || item.resource_id}</strong>
          <label>Количество {input(item.amount, (value) => resource(item.resource_id, { amount: value || null, source: value ? 'USER' : 'UNKNOWN', confirmed: false }), `${item.resource_id}: количество`, 'w-16')}</label>
          {item.kind === 'STAFF' && <label>Зарплата gross, ₽/мес. {input(item.monthly_gross_salary_rub, (value) => resource(item.resource_id, { monthly_gross_salary_rub: value || null, confirmed: false }), `${item.resource_id}: зарплата`, 'w-24')}</label>}
          <label><input type="checkbox" checked={item.confirmed} disabled={!item.amount || item.source === 'UNKNOWN'} onChange={(event) => resource(item.resource_id, { confirmed: event.target.checked })} /> Подтверждено</label>
        </div>)}
        <div className="mt-3 flex flex-wrap gap-2 rounded border p-2">
          <label>ID ресурса {input(newResource.resource_id, (value) => setNewResource((old) => ({ ...old, resource_id: value })), 'ID общего ресурса', 'w-32')}</label>
          <label>Тип <select className="rounded border p-1" value={newResource.kind} onChange={(event) => setNewResource((old) => ({ ...old, kind: event.target.value }))}>
            {['EQUIPMENT', 'CONVEYOR', 'AREA', 'EXPENSE'].map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select></label>
          <label>Количество {input(newResource.amount, (value) => setNewResource((old) => ({ ...old, amount: value })), 'Количество общего ресурса', 'w-20')}</label>
          <label>Единица {input(newResource.unit, (value) => setNewResource((old) => ({ ...old, unit: value })), 'Единица общего ресурса', 'w-20')}</label>
          <button type="button" className="secondary-action" onClick={() => {
            if (!newResource.resource_id.trim() || !newResource.amount || draft.resources.some((item) => item.resource_id === newResource.resource_id.trim())) {
              setError('Укажите уникальный ID и количество ресурса.'); return;
            }
            setDraft((current) => ({ ...current, resources: [...current.resources, {
              resource_id: newResource.resource_id.trim(), kind: newResource.kind, role_code: null,
              amount: newResource.amount, unit: newResource.unit, monthly_gross_salary_rub: null,
              source: 'USER', source_ref: null, confirmed: false,
            }] }));
            setNewResource({ resource_id: '', kind: 'EQUIPMENT', amount: '', unit: 'ед.' }); setError('');
          }}>Добавить общий ресурс</button>
        </div>
        {draft.resources.filter((item) => item.kind !== 'STAFF').map((item) => <div key={`${item.resource_id}.links`} className="mt-2 rounded border p-2">
          <strong>{item.resource_id}</strong> · связан с: {draft.flows.filter((flowItem) => flowItem.resource_ids.includes(item.resource_id)).map((flowItem) => record.capabilities.rows.find((row) => row.code === flowItem.code)?.label).join(', ') || 'нет операций'}
          <div className="mt-1 flex flex-wrap gap-2">{draft.flows.map((flowItem) => <label key={flowItem.code}><input type="checkbox" checked={flowItem.resource_ids.includes(item.resource_id)} onChange={(event) => flow(flowItem.code, { resource_ids: event.target.checked
            ? [...flowItem.resource_ids, item.resource_id] : flowItem.resource_ids.filter((id) => id !== item.resource_id) })} /> {record.capabilities.rows.find((row) => row.code === flowItem.code)?.label}</label>)}</div>
        </div>)}
      </details>
      <details><summary className="cursor-pointer font-semibold">Явные связи между единицами</summary>
        <p>Без подтверждённого коэффициента 100 000 строк отбора остаются строками, а паллетные рейсы — отдельным входом.</p>
        {draft.conversions.map((item, index) => <div key={index} className="mt-2 flex flex-wrap gap-2 rounded border p-2">
          <select aria-label="Откуда" value={item.from_code} onChange={(event) => conversion(index, { from_code: event.target.value })}>{draft.flows.map((flowItem) => <option key={flowItem.code} value={flowItem.code}>{flowItem.code}</option>)}</select>
          <span>→</span><select aria-label="Куда" value={item.to_code} onChange={(event) => conversion(index, { to_code: event.target.value })}>{draft.flows.map((flowItem) => <option key={flowItem.code} value={flowItem.code}>{flowItem.code}</option>)}</select>
          <label>Единиц целевого потока на единицу исходного {input(item.factor, (value) => conversion(index, { factor: value }), 'Коэффициент связи', 'w-20')}</label>
          <label>Источник связи {input(item.source_ref, (value) => conversion(index, { source_ref: value || null }), 'Источник коэффициента', 'w-40')}</label>
          <label><input type="checkbox" checked={item.confirmed} onChange={(event) => conversion(index, { confirmed: event.target.checked })} /> Подтверждаю связь</label>
          <button className="underline" type="button" onClick={() => setDraft((current) => ({ ...current, conversions: current.conversions.filter((_, at) => at !== index) }))}>Удалить</button>
        </div>)}
        <button type="button" className="secondary-action mt-2" onClick={() => setDraft((current) => ({ ...current, conversions: [...current.conversions, { from_code: 'picking_lines', to_code: 'shipping', factor: '', source: 'USER', source_ref: null, confirmed: false }] }))}>Добавить связь</button>
      </details>
      <button type="button" className="primary-action" disabled={busy} onClick={save}>{busy ? 'Сохраняем…' : 'Сохранить новую версию цепочки'}</button>
      <p className="text-xs">Карта операций описывает охват. Она не запускает формулы для отбора, упаковки или паллетизации без активной пригодной позиции и отдельного подтверждённого расчёта.</p>
    </>}
  </section>;
}
