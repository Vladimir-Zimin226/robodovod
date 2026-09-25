import { useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import { buildPartialEconomicsRunRequest } from '../economicsInputV2';
import { ECONOMICS_CONDITIONS, economicsReadiness } from '../economicsReadiness';
import {
  WAREHOUSE_ECONOMICS_DEMO, applyWarehouseEconomicsDemo, chooseUserField,
  confirmAllEconomicsAssumptions, confirmEconomicsAssumption, editEconomicsField,
  proposeDemoField,
} from '../economicsDemoAssumptions';
import { fieldPresentation } from '../presentation';

const API = import.meta.env.VITE_API_URL || '';
const today = () => new Date().toISOString().slice(0, 10);
const FIELDS = [
  ['Труд', 'manualUnitsPerShift', 'manual_units_per_shift', 'Ручная производительность', 'ед./смену', 'Для сравнения труда; например 100.', 'Норма или замер'],
  ['Труд', 'controlHeadcount', 'control_headcount', 'Диспетчеры сейчас', 'чел.', 'Для добавочной численности; например 0.', 'Штатное расписание'],
  ['Труд', 'controlMonthlyGross', 'control_monthly_gross', 'Зарплата диспетчера gross', '₽/чел./мес.', 'Для расходов на пульт; например 100000.', 'ФОТ'],
  ['Труд', 'technicianHeadcount', 'technician_headcount', 'Техники сейчас', 'чел.', 'Для дополнительной техподдержки; например 0.', 'Штатное расписание'],
  ['Труд', 'technicianMonthlyGross', 'technician_monthly_gross', 'Зарплата техника gross', '₽/чел./мес.', 'Для расходов на поддержку; например 120000.', 'ФОТ'],
  ['Покупка', 'implementationCost', 'implementation_cost_total_gross', 'Внедрение и интеграция', '₽ всего, gross', 'Разовый расход; например 500000.', 'Смета или допущение'],
  ['Покупка', 'annualService', 'annual_service_per_robot_gross', 'Сервис одного робота', '₽/год, gross', 'Ежегодный расход; например 120000.', 'Договор или допущение'],
  ['Покупка', 'warrantyYears', 'warranty_years', 'Гарантия', 'лет', 'Влияет на жизненный цикл; например 1.', 'Условия поставки'],
  ['Покупка', 'averagePowerW', 'average_power_w', 'Средняя мощность робота', 'Вт', 'Для электроэнергии; например 1000.', 'Паспорт, замер или допущение'],
  ['Покупка', 'sharedSiteCapital', 'shared_site_capital_gross', 'Общие разовые расходы площадки', '₽ всего, gross', 'Инфраструктура парка; 0, если расходов нет.', 'Смета площадки'],
  ['Покупка', 'sharedAnnualCost', 'shared_annual_cost_gross', 'Общие ежегодные расходы площадки', '₽/год, gross', 'Общие затраты; 0, если расходов нет.', 'Бюджет площадки'],
  ['Покупка', 'horizonYears', 'horizon_years', 'Горизонт оценки', 'лет, 5–15', 'Период NPV; например 5.', 'План проекта'],
  ['Покупка', 'discountRate', 'discount_rate', 'Ставка дисконтирования', 'доля, 0–1', 'Будущие денежные потоки; 0.15 = 15%.', 'Финансовая политика'],
  ['RaaS', 'raasMonthly', 'raas_monthly_per_robot_gross', 'Тариф RaaS', '₽/робот/мес., gross', 'Для сравнения с покупкой; например 180000.', 'Договор или допущение'],
  ['RaaS', 'raasContractMonths', 'raas_contract_months', 'Срок договора', 'мес.', 'Должен покрывать горизонт; например 60.', 'Проект договора'],
  ['Визуализация', 'startSeconds', 'start_seconds_from_midnight', 'Начало смены', 'сек. от 00:00', 'Для полной версии сценария; 28800 = 08:00.', 'График работы'],
];
const CHECKS = [
  ['Труд', 'grossConfirm', 'role_salaries_confirmed_as_monthly_gross', 'Подтверждаю, что зарплаты ролей и этой формы указаны за месяц до удержаний.'],
  ['Покупка', 'currencyConfirm', 'organizer_price_currency_rub_confirmed', 'Для сценария трактую цену организаторов как рубли. Это не оферта поставщика.'],
  ['Покупка', 'initialBatteryConfirm', 'initial_battery_in_robot_price_confirmed', 'Для сценария начальная батарея включена в цену робота.'],
  ['Покупка', 'batteryServiceConfirm', 'battery_replacements_in_service_confirmed', 'Для сценария замены батареи включены в сервис.'],
  ['RaaS', 'raasScopeConfirm', 'raas_vendor_scope_confirmed', 'Для сценария RaaS включает оборудование, батареи, зарядку, обслуживание, ПО и интеграцию. Это не факт поставщика.'],
];
const defaults = { evaluationDate: today(), primaryRoleId: '', raasInfrastructureOwner: '', timezone: '', sources: {}, assumptions: {}, userValues: {} };
function restored(capacityRunId, input) {
  const values = { ...defaults, capacityRunId, sources: { ...(input?.field_sources || {}) },
    assumptions: { ...(input?.assumption_evidence || {}) }, userValues: {} };
  FIELDS.forEach(([, key, server]) => { values[key] = String(input?.[server] ?? ''); });
  CHECKS.forEach(([, key, server]) => { values[key] = input?.[server] === true; });
  if (input) Object.assign(values, { evaluationDate: input.evaluation_date || '', primaryRoleId: input.primary_role_id || '',
    raasInfrastructureOwner: input.raas_infrastructure_owner || '', timezone: input.timezone || '' });
  return values;
}
export default function EconomicsInputsV2({ capacityRequest, capacityRunId, project, onComplete, initialInput, savedResult, sourceRunId }) {
  const [values, setValues] = useState(() => restored(capacityRunId, initialInput));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const scenario = project?.scenarios?.find((item) => item.slot === 'BASE');
  const issues = savedResult?.issues || [];
  const set = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value }));
  const demoEligible = capacityRequest?.process?.process_code === 'warehouse_receiving_shipping';
  const fieldReady = ([, key, server]) => {
    const value = String(values[key] ?? '');
    return value !== '' && !value.includes('..') &&
      ((values.sources[server] || 'USER') !== 'ASSUMPTION' || values.assumptions[server]?.confirmed === true);
  };
  const groupCount = (group) => {
    const fields = FIELDS.filter((item) => item[0] === group && !(item[1] === 'manualUnitsPerShift' && capacityRequest?.process?.scope === 'CLEANING_AREA'));
    return [fields.filter(fieldReady).length, fields.length];
  };
  const allProposed = demoEligible && FIELDS.every(([, key, server]) => values.sources[server] === 'ASSUMPTION' && values[key] !== '' && values.assumptions[server]);
  const readiness = economicsReadiness(values, capacityRequest, FIELDS);
  const goToMissing = () => {
    const condition = readiness.missingConditions[0];
    const missing = condition ? `condition-${condition.key}` :
      readiness.branches.flatMap((branch) => branch.missing).find((field) => !['labour', 'discount_inputs'].includes(field)) || readiness.visualMissing[0];
    const field = document.getElementById(`economics-${missing}`);
    field?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    field?.focus({ preventScroll: true });
    setError(condition ? 'Для полного расчёта подтвердите пять условий ниже после проверки их смысла.'
      : 'Для полного расчёта заполните отмеченные входы. Пустое поле останется неизвестным при частичном сохранении.');
  };
  const submit = async (event) => {
    event?.preventDefault();
    setError(''); setBusy(true);
    try {
      const body = buildPartialEconomicsRunRequest({ values: { ...values, capacityRunId }, capacityRequest, project, scenario, sourceRunId });
      const response = await fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() }, body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.issues?.[0]?.next_step || (typeof payload.detail === 'string' ? payload.detail : 'Серверный расчёт не выполнен.'));
      onComplete(payload);
    } catch (submitError) { setError(submitError.message || 'Не удалось выполнить расчёт.'); }
    finally { setBusy(false); }
  };
  if (!project || !scenario || !capacityRunId) return null;
  const roleRefs = capacityRequest?.process?.role_refs || [];
  return <form className="economics-inputs-v2 mx-auto my-6 max-w-6xl rounded-2xl border p-5 shadow-sm space-y-5" onSubmit={(event) => event.preventDefault()} noValidate aria-label="Расчёт экономики роботизации">
    <header><h2 className="text-xl font-semibold">Экономика: заполните то, что известно</h2>
      <p className="mt-1 text-sm">Пустое поле — неизвестно, 0 — подтверждённый ноль. Диапазон вводите как 500000..800000: он сохранится, но NPV без точечного значения не считается. Для оценки выберите «Допущение»; она не станет фактом поставщика.</p></header>
    <section className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm" aria-label="Источники и полнота входов">
      <h3 className="font-semibold">Откуда взяты значения</h3>
      <p>Параметры объекта и расчёт потребного парка показаны в техническом результате со своими источниками. Здесь «Данные пользователя» — ваш ввод; «Допущение для сценария» — предлагаемое или изменённое вами число. Цена каталога и условия аренды остаются неподтверждёнными коммерческими условиями.</p>
      <p className="mt-2">Расчёт парка: {capacityRunId ? 'сохранён' : 'нужен расчёт'} · Труд: {groupCount('Труд').join('/')} · Покупка: {groupCount('Покупка').join('/')} · Аренда: {groupCount('RaaS').join('/')} · Визуализация: {groupCount('Визуализация').join('/')}. Полноту расчёта окончательно проверяет сервер.</p>
      <p className="mt-2">Общие затраты площадки вводятся один раз для этого сценария. Если вы рассчитали несколько зон отдельно, их NPV и парки нельзя суммировать без модели общих ресурсов и межзональных потоков.</p>
    </section>
    <section className="rounded-xl border border-blue-200 p-4 text-sm" aria-label="Обзор веток перед сохранением">
      <h3 className="font-semibold">Что будет в отчёте</h3>
      <div className="mt-2 grid gap-2 md:grid-cols-2">{readiness.branches.map((branch) => <div key={branch.key} className="rounded border p-2">
        <strong>{branch.label}: {branch.missing.length === 0 ? 'готово к проверке сервером' : readiness.missingConditions.some((condition) => branch.key === 'labour' ? condition.group === 'Труд' : ['purchase', 'raas'].includes(branch.key)) ? 'нужно подтвердить' : 'можно сохранить частично'}</strong>
        {branch.missing.length > 0 && <p>{branch.key === 'capacity' ? '' : `Нужно подтвердить или заполнить: ${branch.missing.filter((field) => !['labour', 'discount_inputs'].includes(field)).map((field) => CHECKS.find((item) => item[1] === field)?.[3] || FIELDS.find((item) => item[2] === field)?.[3] || field).join('; ')}.`}</p>}
      </div>)}</div>
      <p className="mt-2">2D/3D: {readiness.visualMissing.length ? 'нужны начало работы и часовой пояс' : 'входы готовы к проверке сервером'}. Итоговый статус определяет сохранённый серверный результат.</p>
      {!readiness.fullReady && <p className="mt-2 text-amber-900">Если сохранить частично, в PDF/ZIP разделы труда, покупки, RaaS или визуализации с недостающими входами будут помечены «не рассчитано»; NPV для этих веток не появится. Технический результат останется доступен.</p>}
    </section>
    {demoEligible && <section className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm" aria-label="Демо-допущения склада">
      <h3 className="font-semibold">Демо склада</h3>
      <p>{WAREHOUSE_ECONOMICS_DEMO.source}. Дата набора: {WAREHOUSE_ECONOMICS_DEMO.published_on}. Числа можно изменить или очистить.</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" className="secondary-action" onClick={() => setValues((current) => applyWarehouseEconomicsDemo(current, FIELDS))}>Предложить все числа</button>
        <button type="button" className="secondary-action" disabled={!allProposed} onClick={() => setValues(confirmAllEconomicsAssumptions)}>Подтвердить допущения</button>
      </div>
      <p className="mt-2">После предложения проверьте каждое число и подтвердите их. Подтверждения условий gross, цены, батареи и RaaS ниже задаются отдельно.</p>
    </section>}
    {['Труд', 'Покупка', 'RaaS', 'Визуализация'].map((group) => <section key={group} aria-label={group}>
      <h3 className="font-semibold">{group}</h3>
      {group === 'Труд' && roleRefs.length > 1 && <label className="block mt-3 text-sm">Основная роль процесса
        <select value={values.primaryRoleId} onChange={set('primaryRoleId')} className="w-full border rounded p-2"><option value="">Неизвестно</option>{roleRefs.map((id, index) => <option key={id} value={id}>Роль {index + 1}</option>)}</select>
        <small>Для сравнения труда; источник — введённые роли процесса.</small></label>}
      <div className="mt-2 grid gap-3 md:grid-cols-3">{FIELDS.filter((field) => field[0] === group && !(field[1] === 'manualUnitsPerShift' && capacityRequest?.process?.scope === 'CLEANING_AREA')).map(([, key, server, label, unit, why, source]) => {
        const fieldIssues = issues.filter((item) => item.field === server);
        return <div key={key} className="block rounded border border-slate-500/40 p-3 text-sm">
          <strong className="block">{label} <span className="font-normal">· {unit}</span></strong>
          <small className="block mt-1">{why}</small>
          <input id={`economics-${server}`} type="text" inputMode="decimal" aria-label={label} value={values[key]} onChange={(event) => setValues((current) => editEconomicsField(current, key, server, event.target.value, { enableTemplate: demoEligible }))} className="w-full border rounded p-2 mt-2" placeholder="Неизвестно — оставьте пустым" aria-invalid={fieldIssues.some((item) => !['MISSING_INPUT', 'RANGE_ONLY'].includes(item.code))} />
          <small className="block mt-1">Возможный источник: {source}. {['Покупка', 'RaaS'].includes(group) ? 'Коммерческое условие требует отдельной проверки.' : ''}</small>
          <select value={values.sources[server] || 'USER'} onChange={(event) => setValues((current) => event.target.value === 'USER'
            ? chooseUserField(current, key, server) : proposeDemoField(current, key, server, { enableTemplate: demoEligible }))} aria-label={`Тип источника: ${label}`} className="w-full border rounded p-2 mt-1">
            <option value="USER">Данные пользователя</option><option value="ASSUMPTION">Допущение для сценария</option>
          </select>
          {values.sources[server] === 'ASSUMPTION' && <div className="mt-2 rounded bg-amber-50 p-2 text-xs">
            {demoEligible && WAREHOUSE_ECONOMICS_DEMO.fields[server] ? <p>Предложение для «{fieldPresentation(server).label}» от {WAREHOUSE_ECONOMICS_DEMO.published_on}: {WAREHOUSE_ECONOMICS_DEMO.fields[server].value} {WAREHOUSE_ECONOMICS_DEMO.fields[server].unit}. {WAREHOUSE_ECONOMICS_DEMO.fields[server].rationale}. Источник: {WAREHOUSE_ECONOMICS_DEMO.source}.</p>
              : <p>Для этого поля нет шаблона. Введите число вручную и подтвердите его как ваше сценарное допущение.</p>}
            {values[key] !== '' && values.assumptions[server] && <label className="mt-1 flex gap-2"><input type="checkbox" checked={values.assumptions[server].confirmed === true} onChange={(event) => setValues((current) => confirmEconomicsAssumption(current, server, event.target.checked))} />Подтверждаю число {values[key]} для этого сценария</label>}
            {values[key] !== '' && !values.assumptions[server] && <p>Нужно ввести и подтвердить число.</p>}
          </div>}
          {fieldIssues.map((item, index) => <small key={index} className={`block mt-1 ${['MISSING_INPUT', 'RANGE_ONLY'].includes(item.code) ? 'text-amber-900' : 'text-red-700'}`} role="status">{item.message} {item.next_step}</small>)}
        </div>;
      })}</div>
      {group === 'Покупка' && <label className="block mt-3 text-sm">Дата оценки · дата<input id="economics-evaluation_date" type="date" value={values.evaluationDate} onChange={set('evaluationDate')} className="w-full border rounded p-2" /><small>Для привязки цен; источник — дата оценки проекта.</small></label>}
      {group === 'RaaS' && <label className="block mt-3 text-sm">Кто оплачивает инфраструктуру<select id="economics-raas_infrastructure_owner" value={values.raasInfrastructureOwner} onChange={set('raasInfrastructureOwner')} className="w-full border rounded p-2"><option value="">Неизвестно</option><option value="VENDOR">Поставщик</option><option value="CUSTOMER">Заказчик</option></select><small>Для состава затрат; источник — договор или допущение.</small></label>}
      {group === 'Визуализация' && <label className="block mt-3 text-sm">Часовой пояс · IANA<input id="economics-timezone" value={values.timezone} onChange={set('timezone')} className="w-full border rounded p-2" placeholder="Например, Europe/Moscow" /><small>Для полного сценария; пусто — не рассчитано.</small></label>}
    </section>)}
    <section className="rounded-xl border border-amber-300 p-4 text-sm" aria-label="Пять условий экономического сценария">
      <h3 className="font-semibold">Пять условий для денежного расчёта</h3>
      <p>Каждое подтверждение относится только к этому сценарию и не подтверждает условия поставщика. Проверьте смысл условий, затем отметьте каждое отдельно.</p>
      {CHECKS.map(([, key, server, label]) => <label key={key} className="mt-3 flex gap-2 rounded border p-2"><input id={`economics-condition-${key}`} type="checkbox" checked={values[key]} onChange={set(key)} /><span>{label}<small className="block">{ECONOMICS_CONDITIONS.find((item) => item.key === key)?.consequence}</small>{issues.some((item) => item.field === server) && <small className="block text-red-700">Нужно для этой ветки.</small>}</span></label>)}
    </section>
    <p className="text-sm">Пригодность на объекте и закупочная готовность проверяются отдельно. Этот расчёт не подтверждает поставщика и не даёт рекомендации к закупке.</p>
    {error && <p className="text-red-700" role="alert">{error}</p>}
    <div className="flex flex-wrap gap-3"><button type="button" disabled={busy} onClick={readiness.fullReady ? submit : goToMissing} className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white disabled:bg-slate-300">Полный расчёт</button>
      <button type="button" disabled={busy} onClick={submit} className="secondary-action">{busy ? 'Сохраняем…' : 'Сохранить частичный результат'}</button></div>
  </form>;
}
