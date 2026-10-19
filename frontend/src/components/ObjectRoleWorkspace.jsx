import { useEffect, useRef, useState } from 'react';
import AppIcon from './AppIcon';
import { readCsrfCookie } from '../persistenceApi';
import './WarehouseRoleWorkspace.css';

const API = import.meta.env.VITE_API_URL || '';
const NAMES = { WAREHOUSE: 'склада', AIRPORT: 'аэропорта', CLINIC: 'клиники' };
const num = (value) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value || 0));
const money = (value) => value == null ? 'Нужны данные' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(value))} ₽`;

async function request(path, options) {
  const response = await fetch(`${API}${path}`, { credentials: 'include', ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Ошибка ${response.status}`);
  return body;
}

function Field({ label, value, onChange, min = 0, max, hint }) {
  return <label className="wr-field"><span>{label}</span><input type="number" step="any" min={min} max={max} value={value ?? ''}
    onChange={(event) => onChange(event.target.value === '' ? null : event.target.value)} />{hint && <small>{hint}</small>}</label>;
}

function asInput(draft, kind) {
  return { kind, general: draft.general, include_safety_in_conditional: draft.include_safety_in_conditional,
    roles: draft.roles.filter((role) => role.selected && role.works.some((work) => work.selected)).map((role) => ({
      role_code: role.role_code, headcount: role.headcount,
      monthly_employer_cost_rub: role.monthly_employer_cost_rub,
      salary_basis: role.salary_basis, headcount_source: role.headcount_source,
      salary_source: role.salary_source,
      realizable_labor_share: role.realizable_labor_share,
      works: role.works.filter((work) => work.selected).map((work) => Object.fromEntries(Object.entries(work)
        .filter(([key]) => !['selected', 'label'].includes(key)))),
    })) };
}

function Summary({ title, total, warning }) {
  return <section className="wr-portfolio"><h2>{title}</h2>{warning && <p role="alert" className="wr-message wr-message-error">{warning}</p>}
    <div className="wr-portfolio-grid">
      <div><span>Работ / парк</span><strong>{total.work_count} / {total.fleet}</strong></div>
      <div><span>Без роботов: ФОТ этих ролей в год</span><strong>{money(total.baseline_annual_labor_rub)}</strong></div>
      <div><span>Потенциал до коэффициента</span><strong>{num(total.potential_fte)} ставки</strong></div>
      <div><span>После коэффициента / ФОТ в год</span><strong>{num(total.fte_equivalent)} / {money(total.annual_labor_rub)}</strong></div>
      <div><span>Покупка: CAPEX / TCO</span><strong>{money(total.purchase.capex_rub)} / {money(total.purchase.tco_rub)}</strong></div>
      <div><span>Покупка: эффект после сервиса в год</span><strong>{money(total.purchase.annual_net_rub)}</strong></div>
      <div><span>Покупка: NPV / ROI</span><strong>{money(total.purchase.npv_rub)} / {total.purchase.roi_percent == null ? 'N/A' : `${num(total.purchase.roi_percent)}%`}</strong></div>
      <div><span>Аренда: CAPEX / TCO</span><strong>{money(total.raas.capex_rub)} / {money(total.raas.tco_rub)}</strong></div>
      <div><span>Аренда: эффект после тарифа в год</span><strong>{money(total.raas.annual_net_rub)}</strong></div>
      <div><span>Аренда: NPV / ROI на CAPEX</span><strong>{money(total.raas.npv_rub)} / {total.raas.roi_status === 'DEFINED' ? `${num(total.raas.roi_percent)}%` : total.raas.roi_status}</strong></div>
    </div>
    {total.purchase.missing.length > 0 && <p>Для покупки недостаёт: {total.purchase.missing.join(', ')}</p>}
    {total.raas.missing.length > 0 && <p>Для аренды недостаёт: {total.raas.missing.join(', ')}</p>}
  </section>;
}

function CandidateSelection({ role, work, report, onChange }) {
  const resultRole = report.roles.find((item) => item.role_code === role.role_code);
  const calculated = resultRole?.works.find((item) => item.process_code === work.process_code);
  if (!calculated) return null;
  return <div><p>Подбор: {calculated.candidates.length} функциональных кандидатов; выбран {calculated.selected_model_name || 'сценарный тип без модели'}. Парк {calculated.fleet}.</p>
    {calculated.labor_sensitivity?.map((point) => <p key={point.labor_share}>Коэффициент {num(point.labor_share)}: ФОТ {money(point.annual_labor_rub)} · NPV покупки {money(point.purchase_npv_rub)} · NPV аренды {money(point.raas_npv_rub)} · парк {calculated.fleet}</p>)}
    <select value={work.selected_position_id === 'AUTO' ? calculated.selected_position_id : work.selected_position_id}
      onChange={(event) => onChange(event.target.value)}>
      <option value="SCENARIO_TYPE">Сценарный тип без каталожной модели</option><option value="NONE">Без робота</option>
      {calculated.candidates.map((candidate) => <option key={candidate.position_id} value={candidate.position_id}>{candidate.name} · {candidate.maturity_status}</option>)}
    </select><p>Подбор по функции в описании каталога; физическая пригодность и поставка требуют проверки.</p></div>;
}

export function ObjectRoleResult({ report, onEdit }) {
  if (!report || report.schema_version !== 'object-role-analysis-v2') return null;
  const works = report.roles.flatMap((role) => role.works.map((work) => ({ ...work, role_code: role.role_code, role_label: role.label })));
  const maxFleet = Math.max(1, ...works.map((work) => work.fleet));
  return <main className="wr-workspace" aria-label={`Результат расчёта ${NAMES[report.kind]} по ролям`}>
    <header className="wr-hero"><div><p className="wr-kicker">ОБЪЕКТ · РОЛИ · РОБОТЫ · ЭКОНОМИКА</p><h1>Результат для {NAMES[report.kind]}</h1>
      <p>Версия каталога {report.catalog_version}. Сценарные цены, тарифы и выработка требуют проверки.</p></div></header>
    <Summary title="Базовый итог без неподтверждённых работ" total={report.base_total} />
    <Summary title="Общий условный итог" total={report.conditional_total} warning={report.safety_warning} />
    <section className="wr-panel"><h2>Парк и виды работы</h2><p>Длина полосы соответствует числу роботов по отдельному назначению; данные совпадают с расчётом выше.</p>
      <div role="img" aria-label="Парк роботов по ролям и видам работы">
        {works.map((work) => <div key={`${work.role_code}:${work.process_code}`} className="wr-fleet-row">
          <span>{work.role_label}: {work.technical_task}</span><div className="wr-fleet-track"><div style={{ width: `${100 * work.fleet / maxFleet}%` }} /></div><strong>{work.fleet}</strong>
        </div>)}
      </div></section>
    <section className="wr-panel"><h2>Назначения и ограничения</h2><div className="wr-role-grid">{report.roles.map((role) => <article key={role.role_code} className="wr-role-card selected">
      <div className="wr-role-toggle"><span className="wr-role-icon"><AppIcon name={role.role_code} size={26} /></span><span className="wr-role-title"><strong>{role.label}</strong><small>{num(role.headcount)} человек; распределено {num(Number(role.allocated_fraction) * 100)}%</small></span></div>
      <div className="wr-role-body"><p>База оплаты: {role.salary_basis}; расходы работодателя {money(role.monthly_employer_cost_rub)}/мес. на человека. Штат: {role.headcount_source}. Ставка: {role.salary_source}.</p>{role.works.map((work) => <div key={work.process_code} className="wr-work-result"><strong>{work.technical_task}</strong>
        <p>{num(work.daily_volume)} {work.unit}/сутки → {num(work.target_units_per_day)} {work.unit}/сутки · парк {work.fleet} · до коэффициента {num(work.potential_fte)} ставки · после {num(work.fte_equivalent)}</p>
        <p>{work.selected_model_name || 'Сценарный тип без каталожной модели'} · {work.model_status} · {work.calculation_status === 'REFERENCE_ONLY' ? 'Техническая подзадача по допущению ASSUMPTION_V2; не паспортная формула C11.' : work.calculation_status}</p>
        <p>Покупка: NPV {money(work.purchase.npv_rub)}, ROI {work.purchase.roi_percent == null ? 'N/A' : `${num(work.purchase.roi_percent)}%`}; аренда: NPV {money(work.raas.npv_rub)}, ROI {work.raas.roi_status}.</p>
        {work.safety_conditions && <p role="alert" className="wr-message wr-message-error">Условный расчёт: {work.safety_conditions}. Эксплуатация не разрешена этим расчётом.</p>}
        <details><summary>Источники и ручной остаток</summary><p>{work.basis}</p><p>Ручной остаток: {work.residual_operations}</p><p>Выработка: {work.rate_source}; цена: {work.price_source}; аренда: {work.raas_source}; строка {work.evidence_ref}.</p></details>
      </div>)}</div></article>)}</div></section>
    <p className="wr-disclaimer">ROI покупки = (недисконтированный эффект за горизонт − CAPEX) / CAPEX × 100%. NPV дисконтирован. При нулевом CAPEX аренды ROI на CAPEX не определён. Эффект ФОТ — сценарий расходов, а не обязательное сокращение сотрудников.</p>
    {onEdit && <button type="button" className="wr-primary" onClick={onEdit}>Изменить роли и пересчитать</button>}
  </main>;
}

export default function ObjectRoleWorkspace({ kind, activeProject, user, authChecked, projectChoices = [], projectStatus,
  onChooseProject, onOpenProjects, onOpenAccount, onSaved }) {
  const [draft, setDraft] = useState(null);
  const [report, setReport] = useState(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState('loading');
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const sequence = useRef(0);
  const projectId = activeProject?.id;

  useEffect(() => {
    let active = true;
    sequence.current += 1;
    Promise.all([request(`/api/v2/object-roles/${kind}/template`), projectId
      ? request(`/api/v2/projects/${encodeURIComponent(projectId)}/object-roles/${kind}`)
      : Promise.resolve({ version: 0, latest: null })]).then(([template, saved]) => {
      if (!active) return;
      const prior = saved.latest?.input_snapshot;
      const priorRoles = Object.fromEntries((prior?.roles || []).map((role) => [role.role_code, role]));
      setDraft({ general: prior?.general || template.general,
        include_safety_in_conditional: prior?.include_safety_in_conditional ?? true,
        roles: template.roles.map((role) => {
          const old = priorRoles[role.role_code];
          const oldWorks = Object.fromEntries((old?.works || []).map((work) => [work.process_code, work]));
          return { ...role, ...(old || {}), selected: prior ? Boolean(old) : true,
            works: role.works.map((work) => ({ ...work, ...(oldWorks[work.process_code] || {}),
              selected: prior ? Boolean(oldWorks[work.process_code]) : true })) };
        }) });
      setReport(saved.latest?.result_snapshot || null);
      setVersion(saved.version);
      setBusy(''); setDirty(false); setError('');
    }).catch((reason) => { if (active) { setError(reason.message); setBusy(''); } });
    return () => { active = false; sequence.current += 1; };
  }, [kind, projectId]);

  const update = (fn) => { sequence.current += 1; setDraft((current) => fn(current)); setDirty(true); setNotice(''); if (busy === 'preview') setBusy(''); };
  const changeGeneral = (key, value) => update((current) => ({ ...current, general: { ...current.general, [key]: value } }));
  const changeRole = (code, key, value) => update((current) => ({ ...current,
    roles: current.roles.map((role) => role.role_code === code ? { ...role, [key]: value,
      ...(key === 'headcount' ? { headcount_source: 'USER' } : {}),
      ...(key === 'monthly_employer_cost_rub' ? { salary_source: 'USER' } : {}) } : role) }));
  const changeWork = (code, process, key, value) => update((current) => ({ ...current,
    roles: current.roles.map((role) => role.role_code === code ? { ...role,
      works: role.works.map((work) => work.process_code === process ? { ...work, [key]: value,
        ...(key === 'scenario_purchase_price_rub' ? { price_source: 'USER' } : {}),
        ...(key === 'scenario_raas_monthly_rub' ? { raas_source: 'USER' } : {}),
        ...(key === 'robot_units_per_hour' ? { rate_source: 'USER_ASSUMPTION' } : {}) } : work) } : role) }));
  const preview = async (inputDraft = draft) => {
    if (!projectId) { setError('Выберите или создайте проект для расчёта.'); return; }
    const currentSequence = ++sequence.current;
    setBusy('preview'); setError('');
    try {
      const response = await request(`/api/v2/projects/${encodeURIComponent(projectId)}/object-roles/${kind}/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(asInput(inputDraft, kind)),
      });
      if (currentSequence !== sequence.current) return;
      setReport(response); setDirty(false); setNotice('Расчёт выполнен. Проверьте назначения, допущения и оба итога.');
      document.getElementById('object-role-results')?.scrollIntoView({ behavior: 'smooth' });
    } catch (reason) { if (currentSequence === sequence.current) setError(reason.message); }
    finally { if (currentSequence === sequence.current) setBusy(''); }
  };
  const save = async () => {
    if (dirty || !report || !projectId) return;
    const currentSequence = sequence.current;
    setBusy('save'); setError('');
    try {
      const saved = await request(`/api/v2/projects/${encodeURIComponent(projectId)}/object-roles/${kind}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ expected_version: version, expected_catalog_version: report.catalog_version, input: asInput(draft, kind) }),
      });
      setVersion(saved.version);
      if (currentSequence === sequence.current) {
        setReport(saved.latest.result_snapshot);
        setNotice(`Сохранено в проекте, версия ${saved.version}.`); onSaved?.(saved.latest.result_snapshot);
      } else setNotice(`Версия ${saved.version} сохранена. Новые правки нужно пересчитать и сохранить отдельно.`);
    } catch (reason) { setError(reason.message); } finally { setBusy(''); }
  };
  if (busy === 'loading') return <main className="wr-workspace" role="status">Загружаем расчёт по ролям…</main>;
  if (!draft) return <main className="wr-workspace" role="alert">{error}</main>;
  return <main className="wr-workspace" aria-label={`Расчёт ${NAMES[kind]} по ролям`}>
    <header className="wr-hero"><div><p className="wr-kicker">ОБЪЕКТНЫЙ РАСЧЁТ · {kind}</p><h1>Роботы для каждой роли {NAMES[kind]}</h1>
      <p>Выберите сотрудников и настройте каждую работу. Типовые значения — редактируемые допущения, не замеры объекта.</p></div>
      <div className="wr-hero-mark"><AppIcon name={kind.toLowerCase()} size={52} /><span>РОЛИ<br />РАСЧЁТ</span></div></header>
    <div className="wr-progress"><span className="active">01 · Объект</span><span className="active">02 · Роли</span><span>03 · Роботы</span><span>04 · Покупка и аренда</span><span>05 · Результат</span></div>
    {!projectId && <section className="wr-project-note"><strong>Для расчёта нужен проект</strong>
      {!authChecked ? <p>Проверяем вход…</p> : !user ? <button type="button" onClick={onOpenAccount}>Войти или зарегистрироваться</button>
        : projectStatus === 'loading' ? <p>Загружаем проекты…</p> : projectChoices.length ? <select defaultValue="" onChange={(event) => {
          const project = projectChoices.find((row) => row.id === event.target.value); if (project) onChooseProject(project);
        }}><option value="">Выберите проект</option>{projectChoices.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          : <button type="button" onClick={onOpenProjects}>Создать проект</button>}</section>}
    <section className="wr-panel"><h2>Общие условия</h2><div className="wr-fields">
      {[
        ['total_area_m2', 'Площадь объекта, м²'], ['shifts_per_day', 'Смен в сутки'],
        ['hours_per_shift', 'Часов в смене'], ['days_per_year', 'Рабочих дней в году'],
        ['robot_availability', 'Доступность робота, 0–1'], ['fleet_reserve_share', 'Резерв парка, 0–1'],
        ['integration_share', 'Внедрение от цены парка, 0–2'], ['annual_service_share', 'Сервис от цены парка в год, 0–1'],
        ['discount_rate', 'Ставка дисконтирования, 0–1'], ['horizon_years', 'Горизонт, лет'],
        ['raas_setup_rub', 'Вложения заказчика при аренде на одного робота, ₽'],
        ['raas_customer_annual_rub', 'Дополнительные расходы заказчика при аренде, ₽/год на робота'],
        ['gross_to_employer_factor', 'Коэффициент расходов работодателя к gross зарплате'],
      ].map(([key, label]) => <Field key={key} label={label} value={draft.general[key]} onChange={(value) => changeGeneral(key, value)} />)}
    </div><p>При аренде тариф задан по каждой работе; состав услуги и сервис необходимо проверить с поставщиком.</p></section>
    <section className="wr-panel"><h2>Роли и виды работы</h2><p>Коэффициент ФОТ: какая часть высвобождённого времени реально уменьшит расходы? Например, 2 потенциальные ставки × 0,5 = экономия расходов на 1 ставку. При 0 люди перераспределяются, при 1 учитывается весь потенциал. Парк не меняется.</p>
      <div className="wr-role-grid">{draft.roles.map((role) => <article key={role.role_code} className={`wr-role-card${role.selected ? ' selected' : ''}`}>
        <button type="button" className="wr-role-toggle" aria-pressed={role.selected} onClick={() => changeRole(role.role_code, 'selected', !role.selected)}>
          <span className="wr-role-icon"><AppIcon name={role.role_code} size={26} /></span><span className="wr-role-title"><strong>{role.label}</strong><small>{role.works.length} видов работы · {num(role.headcount)} человек</small></span>
          <span className="wr-role-check">{role.selected ? '✓' : '+'}</span></button>
        {role.selected && <div className="wr-role-body"><div className="wr-role-fields">
          <Field label="Один штат роли, человек" value={role.headcount} onChange={(value) => changeRole(role.role_code, 'headcount', value)} />
          <Field label={role.salary_basis === 'GROSS' ? 'Начисленная gross зарплата на человека, ₽/мес.' : 'Расходы работодателя на человека, ₽/мес.'} value={role.monthly_employer_cost_rub} onChange={(value) => changeRole(role.role_code, 'monthly_employer_cost_rub', value)} />
          <Field label="Коэффициент ФОТ роли, 0–1" value={role.realizable_labor_share} max="1" onChange={(value) => changeRole(role.role_code, 'realizable_labor_share', value)} />
          <label className="wr-field"><span>База оплаты</span><select value={role.salary_basis} onChange={(event) => changeRole(role.role_code, 'salary_basis', event.target.value)}><option value="EMPLOYER_COST">Полные расходы работодателя</option><option value="GROSS">Начисленная gross зарплата</option></select></label>
        </div><p>Доли работ: {role.works.map((work) => num(Number(work.allocation_fraction) * 100)).join(' + ')}% одного штата; сумма ≤ 100%.</p>
          <p>Источник штата: {role.headcount_source}. Источник ставки: {role.salary_source}. При gross применяется общий сценарный коэффициент {draft.general.gross_to_employer_factor}.</p>
          {role.works.map((work) => <section key={work.process_code} className="wr-work-editor"><label className="wr-source"><input type="checkbox" checked={work.selected} onChange={(event) => changeWork(role.role_code, work.process_code, 'selected', event.target.checked)} /> Включить этот вид работы в расчёт</label><h3>{work.technical_task}</h3>
            <p>{work.process_code} · {work.calculation_status === 'REFERENCE_ONLY' ? 'Сценарная техническая подзадача ASSUMPTION_V2, не формула C11' : work.calculation_status}</p>
            {work.safety_conditions && <p role="alert" className="wr-message wr-message-error">Условный расчёт: {work.safety_conditions}. Эксплуатация не подтверждена.</p>}
            {work.selected && <>
            <div className="wr-role-fields">
              <Field label={`Объём, ${work.unit}/сутки`} value={work.daily_volume} onChange={(value) => changeWork(role.role_code, work.process_code, 'daily_volume', value)} />
              <Field label={`Выработка человека, ${work.unit}/смена`} value={work.manual_units_per_person_shift} onChange={(value) => changeWork(role.role_code, work.process_code, 'manual_units_per_person_shift', value)} />
              <Field label="Доля времени роли на работу, 0–1" value={work.allocation_fraction} max="1" onChange={(value) => changeWork(role.role_code, work.process_code, 'allocation_fraction', value)} />
              <Field label="Роботизируемая доля этой работы, 0–1" value={work.robotizable_share} max="1" onChange={(value) => changeWork(role.role_code, work.process_code, 'robotizable_share', value)} />
              <Field label={`Выработка робота по допущению, ${work.unit}/час`} value={work.robot_units_per_hour} onChange={(value) => changeWork(role.role_code, work.process_code, 'robot_units_per_hour', value)} />
              <Field label="Сценарная цена покупки, ₽/робот" value={work.scenario_purchase_price_rub} onChange={(value) => changeWork(role.role_code, work.process_code, 'scenario_purchase_price_rub', value)} />
              <Field label="Сценарный тариф RaaS, ₽/мес. на робота" value={work.scenario_raas_monthly_rub} onChange={(value) => changeWork(role.role_code, work.process_code, 'scenario_raas_monthly_rub', value)} />
            </div><label className="wr-field"><span>Техническая подзадача</span><input value={work.technical_task} onChange={(event) => changeWork(role.role_code, work.process_code, 'technical_task', event.target.value)} /></label>
            <details><summary>Основания и ручной остаток</summary><label className="wr-field"><span>Основание спроса и допущений</span><textarea value={work.basis} rows="3" onChange={(event) => changeWork(role.role_code, work.process_code, 'basis', event.target.value)} /></label>
              <label className="wr-field"><span>Что остаётся человеку</span><textarea value={work.residual_operations} rows="2" onChange={(event) => changeWork(role.role_code, work.process_code, 'residual_operations', event.target.value)} /></label>
              <p>Цена и тариф — бюджетные допущения, если не введены пользователем. Отдельное предложение поставщика не предоставлено.</p></details>
            {report && !dirty && <CandidateSelection role={role} work={work} report={report}
              onChange={(value) => changeWork(role.role_code, work.process_code, 'selected_position_id', value)} />}
            </>}
          </section>)}
        </div>}</article>)}</div>
      <label className="wr-source"><input type="checkbox" checked={draft.include_safety_in_conditional} onChange={(event) => update((current) => ({ ...current, include_safety_in_conditional: event.target.checked }))} /> Включать неподтверждённые safety-работы в общий условный итог</label>
      <div className="wr-actions"><button type="button" className="wr-primary" disabled={busy !== '' || !projectId || !draft.roles.some((role) => role.selected && role.works.some((work) => work.selected))} onClick={() => preview()}>{busy === 'preview' ? 'Считаем…' : 'Подобрать и рассчитать все выбранные работы'}</button></div>
    </section>
    {error && <p role="alert" className="wr-message wr-message-error">{error}</p>}{notice && <p role="status" className="wr-message wr-message-ok">{notice}</p>}
    {report && <div id="object-role-results" className={dirty ? 'wr-results-stale' : ''}><ObjectRoleResult report={report} />
      {dirty && <p role="status">Данные изменены. Пересчитайте перед сохранением.</p>}
      <button type="button" className="wr-primary" disabled={dirty || busy !== ''} onClick={save}>{busy === 'save' ? 'Сохраняем…' : 'Сохранить расчёт в проекте'}</button>
      {version > 0 && <span className="wr-version">Версия {version}</span>}
    </div>}
  </main>;
}
