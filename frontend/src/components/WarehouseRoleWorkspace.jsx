import { useEffect, useRef, useState } from 'react';
import AppIcon from './AppIcon';
import { readCsrfCookie } from '../persistenceApi';
import { readableBasis, sourceLabel } from '../roleSourcePresentation';
import './WarehouseRoleWorkspace.css';

const API = import.meta.env.VITE_API_URL || '';
const GUEST_DRAFT_KEY = 'robodovod:warehouse-role-guest-draft-v1';
const money = (value) => value == null ? 'Нужны данные' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(value))} ₽`;
const decimal = (value) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value));
const UNIT = { pallet: 'паллет', pick: 'операций отбора', item: 'единиц', m2: 'м²' };
const GENERAL_FIELDS = [
  ['total_area_m2', 'Площадь склада, м²', 'Контекст объекта; уборка считается по объёму работы уборщиков ниже'],
  ['shifts_per_day', 'Смен в сутки', 'Сколько смен работает склад'],
  ['hours_per_shift', 'Часов в смене', 'Продолжительность одной смены'],
  ['days_per_year', 'Рабочих дней в году', 'Для годового объёма и часов; ФОТ основан на месячной зарплате'],
];
const ASSUMPTION_FIELDS = [
  ['robot_availability', 'Доступность робота, 0–1'],
  ['fleet_reserve_share', 'Резерв парка, 0–1'],
  ['realizable_labor_share', 'Какая часть высвобождённого времени реально уменьшит расходы на персонал? 0–1'],
  ['raas_setup_rub', 'Вложения заказчика при аренде на одного робота, ₽'],
  ['raas_customer_annual_rub', 'Дополнительные расходы заказчика при аренде, ₽/год на робота'],
  ['integration_share', 'Внедрение от цены парка, 0–2'],
  ['annual_service_share', 'Сервис от цены парка в год, 0–1'],
  ['discount_rate', 'Ставка дисконтирования, 0–1'],
  ['horizon_years', 'Горизонт расчёта, лет'],
];

function makeInput(draft) {
  return {
    general: draft.general,
    roles: draft.roles.filter((row) => row.selected).map((row) => ({
      role_code: row.role_code, headcount: row.headcount,
      monthly_employer_cost_rub: row.monthly_employer_cost_rub,
      daily_volume: row.daily_volume,
      manual_units_per_person_shift: row.manual_units_per_person_shift,
      robotizable_share: row.robotizable_share,
      source: row.source, basis: row.basis, realizable_labor_share: row.realizable_labor_share || null,
    })),
    selected_positions: Object.fromEntries(Object.entries(draft.selected_positions)
      .filter(([code]) => draft.roles.some((row) => row.role_code === code && row.selected))),
    overrides: draft.overrides.filter((item) => draft.roles.some((row) => row.role_code === item.role_code && row.selected)),
  };
}

async function request(path, options) {
  const response = await fetch(`${API}${path}`, { credentials: 'include', ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item) => `${item.loc?.at(-1) || 'Поле'}: ${item.msg}`).join('; ') : `Ошибка ${response.status}`);
  }
  return body;
}

function Field({ label, value, onChange, hint, min = '0', max, step = 'any' }) {
  return <label className="wr-field"><span>{label}</span><input type="number" inputMode="decimal" min={min} max={max}
    step={step} value={value ?? ''} onChange={(event) => onChange(event.target.value)} />{hint && <small>{hint}</small>}</label>;
}

export default function WarehouseRoleWorkspace({ activeProject, user, authChecked, projectChoices = [], projectStatus,
  onChooseProject, onOpenProjects, onOpenAccount, onSaved, onPreview, onInvalidated, onContinue, initialReport }) {
  const [draft, setDraft] = useState(null);
  const [report, setReport] = useState(null);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dirty, setDirty] = useState(false);
  const [unsavedPreview, setUnsavedPreview] = useState(false);
  const [expandedRoles, setExpandedRoles] = useState({});
  const sequence = useRef(0);
  const initialReportRef = useRef(initialReport);
  const onPreviewRef = useRef(onPreview);
  useEffect(() => { initialReportRef.current = initialReport; onPreviewRef.current = onPreview; }, [initialReport, onPreview]);
  const projectId = activeProject?.id;
  const draftKey = `${GUEST_DRAFT_KEY}:${projectId || 'guest'}`;

  useEffect(() => {
    let active = true;
    sequence.current += 1;
    Promise.all([request('/api/v2/warehouse-roles/template'), projectId
      ? request(`/api/v2/projects/${encodeURIComponent(projectId)}/warehouse-roles`)
      : Promise.resolve({ version: 0, latest: null })])
      .then(([template, saved]) => {
        if (!active) return;
        const savedInput = saved.latest?.input_snapshot;
        let sessionDraft = null;
        try { sessionDraft = JSON.parse(sessionStorage.getItem(draftKey) || 'null'); }
        catch { sessionDraft = null; }
        const sourceInput = sessionDraft || savedInput;
        const byCode = Object.fromEntries((sourceInput?.roles || []).map((role) => [role.role_code, role]));
        setDraft({
          general: sourceInput?.general || template.general,
          roles: template.roles.map((row) => ({ ...row, ...(byCode[row.role_code] || {}),
            selected: sessionDraft ? Boolean(byCode[row.role_code]?.selected) : Boolean(byCode[row.role_code]) })),
          selected_positions: sourceInput?.selected_positions || {},
          overrides: sourceInput?.overrides || [],
        });
        setReport(initialReportRef.current || saved.latest?.result_snapshot || null);
        setVersion(saved.version);
        setDirty(Boolean(sessionDraft && !initialReportRef.current));
        setUnsavedPreview(Boolean(sessionDraft && initialReportRef.current));
        if (saved.latest?.result_snapshot && !sessionDraft && !initialReportRef.current) onPreviewRef.current?.(saved.latest.result_snapshot);
        setLoading(false);
      })
      .catch((reason) => { if (active) { setError(reason.message); setLoading(false); } });
    return () => { active = false; sequence.current += 1; };
  }, [projectId, draftKey]);

  useEffect(() => {
    if (!draft) return;
    try {
      if (dirty || unsavedPreview) sessionStorage.setItem(draftKey, JSON.stringify(draft));
      else sessionStorage.removeItem(draftKey);
    } catch { /* The calculator still works when browser storage is unavailable. */ }
  }, [draft, dirty, draftKey, unsavedPreview]);

  const change = (updater) => {
    sequence.current += 1;
    onInvalidated?.();
    setDraft((current) => updater(current));
    setDirty(true);
    setNotice('');
    if (busy === 'preview') setBusy('');
  };
  const changeGeneral = (field, value) => change((current) => ({ ...current,
    general: { ...current.general, [field]: value } }));
  const changeRole = (code, field, value) => change((current) => ({ ...current,
    roles: current.roles.map((row) => row.role_code === code ? { ...row, [field]: value } : row) }));
  const toggleRole = (code) => change((current) => ({ ...current,
    roles: current.roles.map((row) => row.role_code === code ? { ...row, selected: !row.selected } : row),
    selected_positions: Object.fromEntries(Object.entries(current.selected_positions).filter(([key]) => key !== code)),
    overrides: current.overrides.filter((item) => item.role_code !== code),
  }));
  const changeOverride = (roleCode, positionId, field, value) => change((current) => {
    const other = current.overrides.filter((row) => row.role_code !== roleCode || row.position_id !== positionId);
    const prior = current.overrides.find((row) => row.role_code === roleCode && row.position_id === positionId);
    const next = { ...prior, role_code: roleCode, position_id: positionId, [field]: value === '' ? null : value };
    if (field === 'price_rub' && value !== '') next.omit_purchase_price = false;
    if (field === 'raas_monthly_rub' && value !== '') next.omit_raas_tariff = false;
    return { ...current, overrides: [...other, next] };
  });

  const preview = async (nextDraft = draft) => {
    if (!projectId) { setError('Выберите проект, чтобы рассчитать и сохранить склад.'); return; }
    if (!nextDraft.roles.some((row) => row.selected)) { setError('Отметьте хотя бы одну роль склада.'); return; }
    const currentSequence = ++sequence.current;
    setBusy('preview'); setError(''); setNotice('');
    try {
      const result = await request(`/api/v2/projects/${encodeURIComponent(projectId)}/warehouse-roles/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(makeInput(nextDraft)),
      });
      if (currentSequence !== sequence.current) return;
      setDraft((current) => ({ ...current, selected_positions: {
        ...current.selected_positions,
        ...Object.fromEntries(result.roles.filter((role) => role.selected_position_id
          && !Object.hasOwn(current.selected_positions, role.role_code))
          .map((role) => [role.role_code, role.selected_position_id])),
      } }));
      setReport(result);
      setDirty(false);
      setUnsavedPreview(true);
      onPreview?.(result);
      setNotice(`Проверены ${result.catalog_positions_checked} позиций активного каталога для каждой выбранной роли.`);
      document.getElementById('wr-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (reason) {
      if (currentSequence === sequence.current) setError(reason.message);
    } finally {
      if (currentSequence === sequence.current) setBusy('');
    }
  };

  const chooseCandidate = (roleCode, positionId) => {
    const next = { ...draft, selected_positions: { ...draft.selected_positions, [roleCode]: positionId } };
    change(() => next);
    preview(next);
  };
  const clearCandidate = (roleCode) => {
    const next = { ...draft, selected_positions: { ...draft.selected_positions, [roleCode]: 'NONE' },
      overrides: draft.overrides.filter((item) => item.role_code !== roleCode) };
    change(() => next);
    preview(next);
  };

  const save = async () => {
    if (!projectId || !report || dirty) return;
    const currentSequence = sequence.current;
    setBusy('save'); setError('');
    try {
      const saved = await request(`/api/v2/projects/${encodeURIComponent(projectId)}/warehouse-roles`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ expected_version: version, expected_catalog_version: report.catalog_version,
          input: makeInput(draft) }),
      });
      setVersion(saved.version);
      setReport(saved.latest.result_snapshot);
      setUnsavedPreview(false);
      if (currentSequence === sequence.current) {
        try { sessionStorage.removeItem(draftKey); } catch { /* optional */ }
        setNotice(`Расчёт сохранён в проекте, версия ${saved.version}.`);
        onSaved?.(saved.latest.result_snapshot);
      } else {
        setNotice(`Версия ${saved.version} сохранена. Вы изменили данные во время сохранения — пересчитайте их перед новым сохранением.`);
      }
    } catch (reason) { setError(reason.message); }
    finally { setBusy(''); }
  };

  if (loading) return <div className="wr-workspace wr-loading" role="status">Загружаем роли и сохранённый расчёт…</div>;
  if (!draft) return <div className="wr-workspace wr-error" role="alert">Не удалось открыть складской расчёт: {error}</div>;
  const selectedCount = draft.roles.filter((row) => row.selected).length;

  return <main className="wr-workspace" aria-label="Расчёт склада по ролям">
    <header className="wr-hero">
      <div><p className="wr-kicker">НОВЫЙ РАСЧЁТ · СКЛАД</p><h1>Роботы для каждой роли вашего склада</h1>
        <p>Опишите склад, отметьте сотрудников и сравните роботов для каждого вида работы. Зоны и операции заполнять не нужно.</p></div>
      <div className="wr-hero-mark"><AppIcon name="warehouse" size={54} /><span>ВСЕ РОЛИ<br />ОДИН СКЛАД</span></div>
    </header>


    {!projectId && <section className="wr-project-note"><strong>Для расчёта нужен проект</strong>
      {!authChecked ? <p>Проверяем вход…</p> : !user ? <button type="button" onClick={onOpenAccount}>Войти или зарегистрироваться</button>
        : projectStatus === 'loading' ? <p>Загружаем проекты…</p> : projectChoices.length ? <select defaultValue="" onChange={(event) => {
          const project = projectChoices.find((row) => row.id === event.target.value);
          if (project) onChooseProject(project);
        }}><option value="">Выберите проект</option>{projectChoices.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          : <button type="button" onClick={onOpenProjects}>Создать проект</button>}</section>}

    <section className="wr-panel" aria-labelledby="wr-general-heading"><div className="wr-section-heading"><span className="wr-section-number">01</span>
      <div><h2 id="wr-general-heading">Общие данные склада</h2><p>Один график и общие условия для всех выбранных ролей.</p></div></div>
      <div className="wr-fields">{GENERAL_FIELDS.map(([key, label, hint]) => <Field key={key} label={label} hint={hint}
        value={draft.general[key]} onChange={(value) => changeGeneral(key, value)} />)}</div>
      <details className="wr-assumptions"><summary>Допущения сценария и экономики</summary>
        <p>Например, 2 потенциальные ставки × 0,5 = экономия расходов на 1 ставку; остальные часы перераспределяются. 0 означает отсутствие экономии ФОТ, 1 — полный учёт потенциала. Парк роботов не меняется.</p>
        <label className="wr-field">Тариф RaaS<select value={draft.general.raas_mode || 'FIXED'} onChange={(event) => changeGeneral('raas_mode', event.target.value)}><option value="PERCENT">% цены робота в месяц</option><option value="FIXED">₽/робот/месяц</option></select></label>
        <div className="wr-fields">{draft.general.raas_mode === 'PERCENT'
          ? <Field label="Сценарная аренда, % цены робота в месяц" value={draft.general.raas_percent_monthly} max="100" onChange={(value) => changeGeneral('raas_percent_monthly', value)} hint="2% от 3 млн ₽ = 60 тыс. ₽/робот/мес. Это тариф услуги, не ставка кредита." />
          : <Field label="Сценарная аренда, ₽/робот/мес." value={draft.general.raas_monthly_rub} onChange={(value) => changeGeneral('raas_monthly_rub', value)} />}</div>
        <div className="wr-fields">{ASSUMPTION_FIELDS.map(([key, label]) => <Field key={key} label={label}
          value={draft.general[key]} onChange={(value) => changeGeneral(key, value)} />)}</div></details>
    </section>

    <section className="wr-panel" aria-labelledby="wr-roles-heading"><div className="wr-section-heading"><span className="wr-section-number">02</span>
      <div><h2 id="wr-roles-heading">Кто работает на складе?</h2><p>Выбрано {selectedCount} из {draft.roles.length}. Данные шаблона — допущения; замените их своими, если они известны.</p></div></div>
      <div className="wr-role-grid">{draft.roles.map((row) => <article key={row.role_code} className={`wr-role-card${row.selected ? ' selected' : ''}`}>
        <button type="button" className="wr-role-toggle" aria-pressed={row.selected} onClick={() => toggleRole(row.role_code)}>
          <span className="wr-role-icon"><AppIcon name={row.role_code} size={28} /></span><span className="wr-role-title"><strong>{row.label}</strong><small>{UNIT[row.unit]} за смену</small></span>
          <span className="wr-role-check" aria-hidden="true">{row.selected ? '✓' : '+'}</span></button>
        {row.selected && <div className="wr-role-body"><div className="wr-role-fields">
          <Field label="Человек" value={row.headcount} onChange={(value) => changeRole(row.role_code, 'headcount', value)} />
          <Field label="Расходы работодателя, ₽/мес. на человека" value={row.monthly_employer_cost_rub}
            onChange={(value) => changeRole(row.role_code, 'monthly_employer_cost_rub', value)} />
          <Field label={`Объём в сутки, ${UNIT[row.unit]}`} value={row.daily_volume}
            onChange={(value) => changeRole(row.role_code, 'daily_volume', value)} />
          <Field label={`Выработка человека за смену, ${UNIT[row.unit]}`} value={row.manual_units_per_person_shift}
            onChange={(value) => changeRole(row.role_code, 'manual_units_per_person_shift', value)} />
          <Field label="Доля работы для роботизации, 0–1" value={row.robotizable_share} max="1"
            onChange={(value) => changeRole(row.role_code, 'robotizable_share', value)} />
          <Field label="Какая часть высвобождённого времени уменьшит расходы на персонал? 0–1" value={row.realizable_labor_share ?? ''} max="1"
            hint={`Пусто = общее значение ${draft.general.realizable_labor_share}. Это не обещание сокращения людей.`}
            onChange={(value) => changeRole(row.role_code, 'realizable_labor_share', value)} />
        </div><details className="wr-basis"><summary>Откуда взяты числа</summary><p>Численность и объём: {sourceLabel(row.source)}. {readableBasis(row.basis)}</p><p>Оплата: {row.source === 'USER' ? 'Ваши данные' : 'Допущение авторов'}. {readableBasis(row.salary_basis)}</p>
          <label>Основание для вашего расчёта<textarea value={readableBasis(row.basis)} rows="3" onChange={(event) => changeRole(row.role_code, 'basis', event.target.value)} /></label>
          <label className="wr-source"><input type="checkbox" checked={row.source === 'USER'} onChange={(event) => changeRole(row.role_code, 'source', event.target.checked ? 'USER' : 'SCENARIO_ASSUMPTION')} />
            Эти значения проверены по данным моего склада</label></details></div>}
      </article>)}</div>
      <div className="wr-actions"><button type="button" className="wr-primary" disabled={busy !== '' || !selectedCount || !projectId}
        onClick={() => preview()}>{busy === 'preview' ? 'Считаем все роли…' : 'Подобрать и рассчитать роботов'}</button>
        <span>Каждая выбранная роль получит отдельный результат. Каталог просматривается полностью.</span></div>
    </section>

    {error && <p className="wr-message wr-message-error" role="alert">{error}</p>}
    {notice && <p className="wr-message wr-message-ok" role="status">{notice}</p>}
    {dirty && report && <p className="wr-message">Данные изменены. Нажмите «Подобрать и рассчитать роботов», чтобы обновить результат.</p>}

    {report && <section id="wr-results" className={`wr-results${dirty ? ' wr-results-stale' : ''}`} aria-label="Роботы и результат по ролям">
      <div className="wr-actions"><strong>Предпросмотр готов: {report.portfolio.selected_robot_allocations} роботов по назначениям.</strong>
        <button type="button" className="wr-primary" disabled={busy !== '' || dirty} onClick={onContinue}>Продолжить к роботам →</button></div>
      <div className="wr-section-heading"><span className="wr-section-number">03</span><div><h2>Роботы для каждой роли</h2>
        <p>Для каждой роли проверено {report.catalog_positions_checked} позиций активного каталога. Показанные варианты требуют проверки на вашем складе.</p></div></div>
      {report.roles.map((role) => {
        const selected = role.candidates.find((item) => item.position_id === role.selected_position_id);
        const visible = expandedRoles[role.role_code] ? role.candidates : [
          ...role.candidates.slice(0, 4),
          ...role.candidates.filter((item, index) => index >= 4 && item.position_id === role.selected_position_id),
        ];
        const override = draft.overrides.find((item) => item.role_code === role.role_code && item.position_id === selected?.position_id);
        return <article className="wr-result-role" key={role.role_code}><div className="wr-result-head"><span className="wr-role-icon"><AppIcon name={role.role_code} size={24} /></span>
          <div><h3>{role.label}</h3><p>{role.candidates.length} вариантов · {role.excluded_count} исключено после просмотра каталога · {decimal(role.annual_volume)} {UNIT[role.unit]}/год</p></div>
          <span className="wr-result-count">{role.candidates.length}</span></div>
          {!role.candidates.length ? <p className="wr-empty">В текущем каталоге не нашлось позиции с признаком работы этой роли. Роль сохранена в результате; неподходящий робот не подставляется.</p>
            : <><div className="wr-candidate-grid">{visible.map((candidate, index) => <button type="button" key={candidate.position_id}
              className={`wr-candidate${candidate.position_id === role.selected_position_id ? ' chosen' : ''}`}
              onClick={() => chooseCandidate(role.role_code, candidate.position_id)}>
              <span className="wr-candidate-top"><strong>{candidate.name}</strong><span>{candidate.status === 'RESEARCH_ONLY' ? 'Разработка' : candidate.maturity_status === 'PILOTING' ? 'Пилот' : index === 0 ? 'Первый для проверки' : 'Вариант'}</span></span>
              <small>{candidate.manufacturer || 'Производитель не указан'}{candidate.source_row_number ? ` · строка каталога ${candidate.source_row_number}` : ''}</small>
              <span className="wr-candidate-metrics"><span><b>{candidate.fleet}</b> {candidate.rate_source === 'SCENARIO_ASSUMPTION' ? 'роботов по допущению' : 'роботов'}</span><span><b>{decimal(candidate.fte_equivalent)}</b> ставки*</span></span>
              <span className="wr-candidate-bottom"><span>{candidate.rate_source === 'SCENARIO_ASSUMPTION' ? 'Выработка: допущение' : candidate.rate_source === 'USER' ? 'Выработка: ваша' : 'Выработка: каталог'}</span>
                <span>{candidate.price_rub == null ? 'Цена неизвестна' : `Цена ${money(candidate.price_rub)}`}</span></span>
            </button>)}</div>
              {role.candidates.length > 4 && <button type="button" className="wr-more" onClick={() => setExpandedRoles((current) => ({ ...current, [role.role_code]: !current[role.role_code] }))}>
                {expandedRoles[role.role_code] ? 'Свернуть список' : `Показать все ${role.candidates.length} вариантов`}</button>}
              {selected && <div className="wr-selected-detail"><h4>Выбранный вариант: {selected.name}</h4>
                <div className="wr-detail-metrics"><span>{selected.rate_source === 'SCENARIO_ASSUMPTION' ? 'Сценарный парк' : 'Расчётный парк'} <strong>{selected.fleet}</strong></span><span>До коэффициента <strong>{decimal(selected.potential_fte ?? selected.fte_equivalent)} ставки</strong></span><span>После коэффициента <strong>{decimal(selected.fte_equivalent)} ставки*</strong></span>
                  <span>Годовой ФОТ эквивалент <strong>{money(selected.annual_labor_potential_rub)}</strong></span>
                  <span>Покупка: CAPEX <strong>{money(selected.capex_rub)}</strong></span><span>Покупка: NPV <strong>{money(selected.npv_rub)}</strong></span><span>Покупка: ROI за {report.general?.horizon_years || draft.general.horizon_years} лет <strong>{selected.purchase_roi_percent == null ? report.schema_version === 'warehouse-role-analysis-v1' ? 'Пересчитайте старую версию' : 'Нужна цена' : `${decimal(selected.purchase_roi_percent)}%`}</strong></span><span>Аренда: NPV <strong>{money(selected.raas_npv_rub)}</strong></span></div>
                <p className="wr-disclaimer">Аренда: ROI на CAPEX {selected.raas_roi_percent == null && Number(selected.raas_capex_rub) === 0 ? 'N/A — вложения заказчика равны нулю' : `${decimal(selected.raas_roi_percent)}%`}. Чувствительность ФОТ при 0 / 0,5 / 1: {money(0)} / {money(Number(selected.potential_fte ?? 0) * Number(role.monthly_employer_cost_rub) * 6)} / {money(Number(selected.potential_fte ?? 0) * Number(role.monthly_employer_cost_rub) * 12)} в год; парк {selected.fleet} во всех трёх случаях.</p>
                {selected.fleet_formula && <p className="wr-disclaimer">Сценарный парк {selected.fleet} = округление вверх ({decimal(selected.fleet_formula.target_units_per_day)} {UNIT[selected.unit]}/сутки ÷ ({decimal(selected.fleet_formula.robot_units_per_hour)} {UNIT[selected.unit]}/час × {decimal(selected.fleet_formula.hours_per_shift)} ч × {selected.fleet_formula.shifts_per_day} смен × {decimal(selected.fleet_formula.robot_availability)} доступности) × (1 + {decimal(selected.fleet_formula.fleet_reserve_share)} резерва)). Скорость: {selected.rate_source === 'SCENARIO_ASSUMPTION' ? 'сценарное допущение' : 'проверенный факт каталога'}.</p>}
                {selected.demand_warning && <p role="alert" className="wr-message wr-message-error">{selected.demand_warning} Указано {decimal(role.daily_volume)} {UNIT[selected.unit]}/сутки при штатной выработке {decimal(selected.manual_capacity_units_per_day)} {UNIT[selected.unit]}/сутки.</p>}
                {selected.labor_sensitivity?.map((point) => <p key={point.labor_share} className="wr-disclaimer">Коэффициент {decimal(point.labor_share)}: ФОТ {money(point.annual_labor_rub)}/год · NPV покупки {money(point.purchase_npv_rub)} · NPV аренды {money(point.raas_npv_rub)} · парк {selected.fleet}</p>)}
                <p>Модель найдена по: {selected.match_basis === 'ROLE_NAME' ? 'названию модели'
                  : selected.match_basis === 'ROLE_DESCRIPTION' ? 'прямому описанию выполняемой работы'
                  : selected.match_basis === 'GENERAL_MANIPULATOR_HINT' ? 'общему типу манипулятора; пригодность для паллетизации не подтверждена'
                  : selected.match_basis === 'ROLE_APPLICATION' ? 'заявленному применению или названию в каталоге'
                  : selected.match_basis === 'CATALOG_TEXT_HINT' ? 'описанию и применению в каталоге' : 'расчётному профилю каталога'}.
                  {selected.rate_basis && ` ${selected.rate_basis}`}</p>
                {selected.work_scope === 'DELIVERY_TO_PICKING_STATION' && <p className="wr-message">Робот подвозит стеллажи к станции; товар выбирает человек. Скорость в операциях отбора/час сейчас только эквивалент обслуживания станции, не паспортная скорость робота. Для подтверждения парка нужны рейсы/час и операций на один подвоз. Доля сэкономленного времени — отдельное допущение.</p>}
                {selected.work_scope === 'PALLET_TRANSPORT_ONLY' && <p className="wr-disclaimer">Робот перемещает паллеты. Погрузка, разгрузка и крепление груза остаются за человеком; доля 25% в шаблоне относится только к перемещению и требует проверки.</p>}
                {selected.maturity_status === 'PILOTING' && <p className="wr-disclaimer">Модель находится на стадии пилотирования. Перед закупкой проверьте доступность поставки и работу на вашем складе.</p>}
                <div className="wr-fields"><Field label={`${selected.work_scope === 'DELIVERY_TO_PICKING_STATION' ? 'Объём отбора, обслуживаемый подвозом' : selected.work_scope === 'PALLET_TRANSPORT_ONLY' ? 'Перевозка паллет' : 'Выработка робота'}, ${UNIT[selected.unit]}/час`} value={override?.units_per_hour ?? ''}
                  hint={`Сейчас ${decimal(selected.robot_units_per_hour)} (${selected.rate_source === 'SCENARIO_ASSUMPTION' ? 'допущение' : 'каталог'}). Оставьте пустым, чтобы использовать его.`}
                  onChange={(value) => changeOverride(role.role_code, selected.position_id, 'units_per_hour', value)} />
                  <Field label="Цена одного робота, ₽" value={override?.price_rub ?? ''}
                    hint={selected.price_rub == null ? 'Для NPV укажите цену.' : `Сейчас ${money(selected.price_rub)} (${selected.price_source === 'CATALOG' ? 'каталог' : selected.price_source === 'SCENARIO_ASSUMPTION' ? 'бюджетное допущение, не предложение поставщика' : 'вы указали'}).`}
                    onChange={(value) => changeOverride(role.role_code, selected.position_id, 'price_rub', value)} />
                  <label className="wr-field">Режим аренды<select value={override?.raas_mode || draft.general.raas_mode || 'FIXED'} onChange={(event) => changeOverride(role.role_code, selected.position_id, 'raas_mode', event.target.value)}><option value="PERCENT">% цены робота в месяц</option><option value="FIXED">₽/робот/месяц</option></select></label>
                  {(override?.raas_mode || draft.general.raas_mode) === 'PERCENT'
                    ? <Field label="Аренда, % цены робота в месяц" value={override?.raas_percent_monthly ?? ''} max="100"
                      hint={`Принято ${decimal(selected.raas_percent_monthly ?? draft.general.raas_percent_monthly)}% от ${money(selected.raas_price_basis_rub)} = ${money(selected.raas_monthly_rub)}/робот/мес.`}
                      onChange={(value) => changeOverride(role.role_code, selected.position_id, 'raas_percent_monthly', value)} />
                    : <Field label="Тариф RaaS на одного робота, ₽/мес." value={override?.raas_monthly_rub ?? ''}
                      hint={`Сейчас ${money(selected.raas_monthly_rub)} (${selected.raas_source === 'USER' ? 'ваша оценка' : 'сценарное допущение'}). Уточните состав услуги и ответственность за сервис.`}
                      onChange={(value) => changeOverride(role.role_code, selected.position_id, 'raas_monthly_rub', value)} />}</div>
                <label className="wr-source"><input type="checkbox" checked={Boolean(override?.omit_purchase_price)} onChange={(event) => changeOverride(role.role_code, selected.position_id, 'omit_purchase_price', event.target.checked)} /> Цена покупки неизвестна — оставить покупку частичной</label>
                <label className="wr-source"><input type="checkbox" checked={Boolean(override?.omit_raas_tariff)} onChange={(event) => changeOverride(role.role_code, selected.position_id, 'omit_raas_tariff', event.target.checked)} /> Тариф аренды неизвестен — оставить аренду частичной</label>
                {dirty && <button type="button" className="wr-recalculate" disabled={busy !== ''} onClick={() => preview()}>Пересчитать с новыми данными</button>}
                {!dirty && <button type="button" className="wr-more" onClick={() => clearCandidate(role.role_code)}>Не включать эту модель в общий итог</button>}
              </div>}</>}
        </article>;
      })}
      <section className="wr-portfolio"><div className="wr-section-heading"><span className="wr-section-number">04</span><div><h2>Итог по складу</h2>
        <p>Одна строка персонала на каждую роль. Выбранные роботы закреплены за ролями отдельными назначениями.</p></div></div>
        <div className="wr-portfolio-grid"><div><span>Выбрано ролей с роботом</span><strong>{report.portfolio.selected_roles} / {report.roles.length}</strong></div>
          <div><span>Роботов по назначениям</span><strong>{report.portfolio.selected_robot_allocations}</strong></div>
          <div><span>Без роботов: ФОТ выбранных ролей в год</span><strong>{money(report.portfolio.baseline_annual_labor_rub)}</strong></div>
          <div><span>Ставки в сценарии*</span><strong>{decimal(report.portfolio.fte_equivalent)}</strong></div>
          <div><span>Потенциал ФОТ в год*</span><strong>{money(report.portfolio.annual_labor_potential_rub)}</strong></div>
          <div><span>Капвложения</span><strong>{money(report.portfolio.capex_rub)}</strong></div>
          <div><span>Покупка: TCO / NPV</span><strong>{money(report.portfolio.purchase_tco_rub)} / {money(report.portfolio.npv_rub)}</strong></div>
          <div><span>Покупка: эффект после сервиса в год</span><strong>{money(report.portfolio.annual_net_rub)}</strong></div>
          <div><span>Покупка: ROI за {report.general?.horizon_years || draft.general.horizon_years} лет</span><strong>{report.portfolio.purchase_roi_percent == null ? report.schema_version === 'warehouse-role-analysis-v1' ? 'Пересчитайте старую версию' : 'Нужна цена' : `${decimal(report.portfolio.purchase_roi_percent)}%`}</strong></div>
          <div><span>Аренда: TCO / NPV</span><strong>{money(report.portfolio.raas_tco_rub)} / {money(report.portfolio.raas_npv_rub)}</strong></div>
          <div><span>Аренда: эффект после тарифа в год</span><strong>{money(report.portfolio.raas_annual_net_rub)}</strong></div>
          <div><span>Аренда: ROI</span><strong>{report.portfolio.raas_roi_percent == null && Number(report.portfolio.raas_capex_rub) === 0 ? 'N/A: CAPEX = 0' : report.portfolio.raas_roi_percent == null ? 'Нужен тариф' : `${decimal(report.portfolio.raas_roi_percent)}%`}</strong></div></div>
        <p className="wr-disclaimer">ROI покупки за {report.general?.horizon_years || draft.general.horizon_years} лет = ({money(report.portfolio.annual_net_rub)} чистого эффекта в год × {report.general?.horizon_years || draft.general.horizon_years} − {money(report.portfolio.capex_rub)} CAPEX) / {money(report.portfolio.capex_rub)} × 100%. NPV учитывает дисконтирование.</p>
        {report.schema_version === 'warehouse-role-analysis-v1' && <p className="wr-message">Это старый сохранённый снимок. Для ROI и процентной аренды нажмите «Пересчитать»; прежний результат не изменён.</p>}
        {report.portfolio.missing_purchase?.length > 0 && <p className="wr-message">Покупка: нужна цена для {report.portfolio.missing_purchase.join(', ')}.</p>}
        {report.portfolio.missing_raas?.length > 0 && <p className="wr-message">Аренда: нужен тариф для {report.portfolio.missing_raas.join(', ')}.</p>}
        <p className="wr-disclaimer">* Потенциал при допущенной доле реализации. Это не подтверждённое сокращение штата. Денежный итог остаётся частичным, если хотя бы у одного выбранного робота нет цены.</p>
        <button type="button" className="wr-primary" disabled={busy !== '' || dirty} onClick={save}>{busy === 'save' ? 'Сохраняем…' : 'Сохранить расчёт в проекте'}</button>
        <button type="button" className="wr-primary" disabled={busy !== '' || dirty} onClick={onContinue}>Продолжить к роботам →</button>
        {version > 0 && <span className="wr-version">Текущая версия в проекте: {version}</span>}
      </section>
      <details className="wr-limitations"><summary>Основания и ограничения расчёта</summary><ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        <p>Версия каталога: {report.catalog_version}.</p></details>
    </section>}
  </main>;
}
