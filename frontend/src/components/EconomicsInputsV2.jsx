import { useEffect, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import { buildPartialEconomicsRunRequest } from '../economicsInputV2';
import { ECONOMICS_CONDITIONS, economicsReadiness } from '../economicsReadiness';
import {
  WAREHOUSE_ECONOMICS_DEMO, applyTypicalObjectEconomics, chooseUserField,
  applyManualProductivityEstimate,
  changeManualProductivityRole,
  confirmEconomicsAssumption, editEconomicsField,
  proposeDemoField,
} from '../economicsDemoAssumptions';
import { fieldPresentation } from '../presentation';
import { MODEL_START_SECONDS, modelTimezone, timezoneChoices } from '../simulationDefaults';
import { workbookEconomics } from '../projectWorkbook';
import { PROCESS_DEFINITIONS } from '../processRoleIntakeV2';
import { ECONOMICS_DEPTHS, depthIndex, valuesAtDepth } from '../economicsDepth';

const API = import.meta.env.VITE_API_URL || '';
const today = () => new Date().toISOString().slice(0, 10);
const FIELDS = [
  ['Труд', 'manualUnitsPerShift', 'manual_units_per_shift', 'Выработка одного сотрудника', 'ед./смену', 'Для F08/F09 и экономии ФОТ; например 100.', 'Замер или подтверждённая оценка F08'],
  ['Труд', 'controlHeadcount', 'control_headcount', 'Диспетчеры сейчас', 'чел.', 'Для добавочной численности; например 0.', 'Штатное расписание'],
  ['Труд', 'controlMonthlyGross', 'control_monthly_gross', 'Зарплата диспетчера gross', '₽/чел./мес.', 'Для расходов на пульт; например 100000.', 'ФОТ'],
  ['Труд', 'technicianHeadcount', 'technician_headcount', 'Техники сейчас', 'чел.', 'Для дополнительной техподдержки; например 0.', 'Штатное расписание'],
  ['Труд', 'technicianMonthlyGross', 'technician_monthly_gross', 'Зарплата техника gross', '₽/чел./мес.', 'Для расходов на поддержку; например 120000.', 'ФОТ'],
  ['Труд', 'controlTransferSupplement', 'control_transfer_monthly_supplement_gross', 'Доплата переведённому диспетчеру', '₽/чел./мес., gross', 'Введите подтверждённый ноль, если доплаты нет.', 'Кадровое решение'],
  ['Труд', 'techTransferSupplement', 'technician_transfer_monthly_supplement_gross', 'Доплата переведённому технику', '₽/чел./мес., gross', 'Введите подтверждённый ноль, если доплаты нет.', 'Кадровое решение'],
  ['Труд', 'technicianContractorAnnual', 'technician_contractor_annual_gross', 'Техподдержка подрядчика', '₽/техник/год, gross', 'Стоимость только непокрытой функции.', 'Договор или допущение'],
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
  ['Визуализация', 'startSeconds', 'start_seconds_from_midnight', 'Начало смены', 'сек. от 00:00', 'Модельное начало, отдельно от кнопки воспроизведения.', 'График работы'],
];
const CHECKS = [
  ['Труд', 'grossConfirm', 'role_salaries_confirmed_as_monthly_gross', 'Подтверждаю, что зарплаты ролей и этой формы указаны за месяц до удержаний.'],
  ['Покупка', 'currencyConfirm', 'organizer_price_currency_rub_confirmed', 'Для сценария трактую цену организаторов как рубли. Это не оферта поставщика.'],
  ['Покупка', 'initialBatteryConfirm', 'initial_battery_in_robot_price_confirmed', 'Для сценария начальная батарея включена в цену робота.'],
  ['Покупка', 'batteryServiceConfirm', 'battery_replacements_in_service_confirmed', 'Для сценария замены батареи включены в сервис.'],
  ['RaaS', 'raasScopeConfirm', 'raas_vendor_scope_confirmed', 'Для сценария RaaS включает оборудование, батареи, зарядку, обслуживание, ПО и интеграцию. Это не факт поставщика.'],
];
const CALCULATION_RULES = [
  ['Труд', 'Годовая прямая стоимость роли = подтверждённая месячная gross зарплата × 12 × множитель текущего реестра. Высвобождение ограничено парком, ролью и пультом.', 'Зарплата роли и график из сохранённого процесса; коэффициенты из версии расчётного реестра. Без зарплаты денежная ветка остаётся частичной.'],
  ['Покупка', 'Разовые затраты = оборудование + подтверждённые статьи внедрения и площадки + резерв. Амортизируемая база исключает резерв.', 'Цена позиции каталога или указанная вами цена; затраты и гарантия из формы; резерв и отдельные нормы из действующего реестра.'],
  ['RaaS', 'Затраты заказчика = его инфраструктура + годовые расходы заказчика + платежи по выбранному тарифу.', 'Тариф, срок и владелец инфраструктуры из формы; состав услуги требует отдельного подтверждения и не является фактом поставщика.'],
  ['Денежный результат', 'NPV проекта = NPV сценария − NPV базы; ROI покупки делится на денежный CAPEX, рентабельность RaaS — на его TCO.', 'Годовые потоки строит сервер из сохранённых труда, парка и затрат. Ставку и горизонт вы подтверждаете в форме.'],
  ['Налог', 'Основной денежный маршрут рассчитывается до налога на прибыль. НДС не пересчитывается единой ставкой: денежная база использует gross цену по принятому условию сценария.', 'Налоговый режим организации в этой форме неизвестен; иллюстративная налоговая ветка не включается в основной NPV.'],
];
const defaults = { calculationDepth: 'BASIC', evaluationDate: today(), primaryRoleId: '', raasInfrastructureOwner: '', timezone: '', purchasePriceOverride: '', purchasePriceSource: '',
  implementationMode: 'FIXED', implementationPercent: '', raasMode: 'FIXED', raasPercentMonthly: '',
  robotsPerControlPost: '', robotsPerDayTechnician: '', rotationFactor: '', technicianPresence: 'DAY_WORKLOAD', robotizableShare: '', residualOperations: '',
  controlMode: '', technicianPurchaseMode: '', technicianRaasMode: '', qualifiedTechTransfer: false,
  sources: {}, assumptions: {}, userValues: {} };
function restored(capacityRunId, input, project) {
  const values = { ...defaults, calculationDepth: input?.calculation_depth || (input ? 'FULL' : 'BASIC'), capacityRunId, sources: { ...(input?.field_sources || {}) },
    assumptions: { ...(input?.assumption_evidence || {}) }, userValues: {} };
  FIELDS.forEach(([, key, server]) => { values[key] = String(input?.[server] ?? ''); });
  values.purchasePriceOverride = String(input?.purchase_price_override_gross ?? '');
  values.purchasePriceSource = input?.purchase_price_source || '';
  CHECKS.forEach(([, key, server]) => { values[key] = input?.[server] === true; });
  if (input) Object.assign(values, { evaluationDate: input.evaluation_date || '', primaryRoleId: input.primary_role_id || '',
    raasInfrastructureOwner: input.raas_infrastructure_owner || '', timezone: Object.hasOwn(input, 'timezone') ? input.timezone : modelTimezone(project),
    startSeconds: input.start_seconds_from_midnight == null ? String(MODEL_START_SECONDS) : String(input.start_seconds_from_midnight) });
  if (['economics-explicit-inputs-v5', 'economics-explicit-inputs-v6'].includes(input?.schema_version)) Object.assign(values, {
    controlMode: input.staffing_purchase?.control_mode || '',
    technicianPurchaseMode: input.staffing_purchase?.technician_mode || '',
    technicianRaasMode: input.staffing_raas?.technician_mode || '',
    qualifiedTechTransfer: input.staffing_purchase?.technician_qualification_confirmed === true
      || input.staffing_raas?.technician_qualification_confirmed === true,
    controlTransferSupplement: input.staffing_purchase?.control_transfer_monthly_supplement_gross || '',
    techTransferSupplement: input.staffing_purchase?.technician_transfer_monthly_supplement_gross
      || input.staffing_raas?.technician_transfer_monthly_supplement_gross || '',
    technicianContractorAnnual: input.staffing_purchase?.technician_contractor_annual_gross
      || input.staffing_raas?.technician_contractor_annual_gross || '',
  });
  if (input?.schema_version === 'economics-explicit-inputs-v6') Object.assign(values, {
    implementationMode: input.implementation_mode || 'FIXED', implementationPercent: input.implementation_percent || '',
    raasMode: input.raas_mode || 'FIXED', raasPercentMonthly: input.raas_percent_monthly || '',
    robotsPerControlPost: input.staffing_policy?.robots_per_control_post || '',
    robotsPerDayTechnician: input.staffing_policy?.robots_per_day_technician || '',
    rotationFactor: input.staffing_policy?.rotation_factor || '',
    technicianPresence: input.staffing_policy?.technician_presence || 'DAY_WORKLOAD',
    robotizableShare: input.work_share?.fraction || '', residualOperations: input.work_share?.residual_operations || '',
  });
  if (!input) Object.assign(values, { startSeconds: String(MODEL_START_SECONDS), timezone: modelTimezone(project) });
  return values;
}
export default function EconomicsInputsV2({ capacityRequest, capacityResult, capacityRunId, project, onComplete, initialInput, savedResult, sourceRunId }) {
  const [values, setValues] = useState(() => restored(capacityRunId, initialInput || workbookEconomics(project?.profile?.file_intake_v2), project));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [manualEstimate, setManualEstimate] = useState(null);
  useEffect(() => {
    if (!project?.id || !capacityRunId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(capacityRunId)}/manual-productivity-estimate`,
      { credentials: 'include', signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then((result) => {
        if (result.source_run_id === capacityRunId && result.input_revision === capacityRequest?.input_revision) setManualEstimate(result);
      })
      .catch((reason) => { if (reason.name !== 'AbortError') setManualEstimate({ status: 'UNAVAILABLE' }); });
    return () => controller.abort();
  }, [project?.id, capacityRunId, capacityRequest?.input_revision]);
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
    const fields = FIELDS.filter((item) => item[0] === group && visibleField(item));
    return [fields.filter(fieldReady).length, fields.length];
  };

  const staffingPreview = savedResult?.staffing_preview || {};
  const fleet = capacityResult?.capacity?.value?.selected_fleet ?? savedResult?.branches?.capacity?.selected_fleet;
  const readiness = economicsReadiness(values, capacityRequest, FIELDS, staffingPreview, fleet);
  const visibleField = (field) => {
    const key = field[1];
    if (key === 'manualUnitsPerShift') return true;
    if (key === 'implementationCost') return values.implementationMode !== 'PERCENT';
    if (key === 'raasMonthly') return values.raasMode !== 'PERCENT';
    if (key === 'controlMonthlyGross') return Number(values.controlHeadcount) > 0 || Object.values(staffingPreview).some((item) => item?.control_additional > 0) || values.controlMode === 'HIRE' && Number(values.controlHeadcount || 0) === 0 && Number(fleet) > 0;
    if (key === 'technicianMonthlyGross') return Number(values.technicianHeadcount) > 0 || Math.ceil(Number(fleet || 0) / 20) > Number(values.technicianHeadcount || 0) && (values.technicianPurchaseMode === 'HIRE' || values.technicianRaasMode === 'HIRE');
    if (key === 'controlTransferSupplement') return values.controlMode === 'TRANSFER';
    if (key === 'techTransferSupplement') return values.technicianPurchaseMode === 'TRANSFER' || values.technicianRaasMode === 'TRANSFER';
    if (key === 'technicianContractorAnnual') return values.technicianPurchaseMode === 'CONTRACTOR' || values.technicianRaasMode === 'CONTRACTOR';
    return true;
  };
  const goToMissing = () => {
    const condition = readiness.missingConditions[0];
    const missing = condition ? `condition-${condition.key}` :
      readiness.branches.flatMap((branch) => branch.missing).find((field) => !['labour', 'discount_inputs'].includes(field)) || readiness.visualMissing[0];
    const field = document.getElementById(`economics-${missing}`);
    for (let parent = field?.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    field?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    field?.focus({ preventScroll: true });
    setError(condition ? 'Для полного расчёта подтвердите пять условий ниже после проверки их смысла.'
      : 'Для полного расчёта заполните отмеченные входы. Пустое поле останется неизвестным при частичном сохранении.');
  };
  const submit = async (event, submitted = values) => {
    event?.preventDefault();
    setError(''); setBusy(true);
    try {
      const prepared = valuesAtDepth(submitted, FIELDS);
      const policyDate = today();
      const body = buildPartialEconomicsRunRequest({ values: { ...prepared, capacityRunId,
        staffingPolicy: prepared.robotsPerControlPost && prepared.robotsPerDayTechnician && prepared.rotationFactor ? {
          schema_version: 'staffing-policy-v2', robots_per_control_post: prepared.robotsPerControlPost,
          robots_per_day_technician: prepared.robotsPerDayTechnician, rotation_factor: prepared.rotationFactor,
          technician_presence: prepared.technicianPresence, source: 'ASSUMPTION',
          basis: 'Принято пользователем для проектного расчёта; проверить нагрузку на объекте', date: policyDate, confirmed: true,
        } : null,
        workShare: prepared.robotizableShare !== '' && prepared.residualOperations ? {
          schema_version: 'robotizable-work-share-v1', fraction: prepared.robotizableShare,
          residual_operations: prepared.residualOperations, source: 'ASSUMPTION',
          basis: 'Принято пользователем для проектного расчёта; проверить остаточные операции на объекте', date: policyDate, confirmed: true,
        } : null }, capacityRequest, project, scenario, sourceRunId });
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
  const process = capacityRequest?.process;
  const processLabel = PROCESS_DEFINITIONS.find((item) => item.code === process?.process_code)?.label || process?.process_code || 'выбранном процессе';
  const selectedRole = capacityRequest?.role_pool?.roles?.find((item) => item.role_id === (values.primaryRoleId || roleRefs[0]));
  const roleLabel = { forklift_driver: 'водителя погрузчика', cleaner: 'уборщика', loader: 'грузчика' }[selectedRole?.role_code]
    || selectedRole?.label || selectedRole?.role_code || 'выбранной роли';
  const estimateShown = manualEstimate?.status === 'ESTIMATE'
    ? new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(manualEstimate.value)) : null;
  return <form className="economics-inputs-v2 mx-auto my-6 max-w-6xl rounded-2xl border p-5 shadow-sm space-y-5" onSubmit={(event) => event.preventDefault()} noValidate aria-label="Расчёт экономики роботизации">
    <header><h2 className="text-xl font-semibold">Рассчитать экономику</h2>
      <p className="mt-1 text-sm">Пустое поле — неизвестно, 0 — подтверждённый ноль. Диапазон вводите как 500000..800000: он сохранится, но NPV без точечного значения не считается. Для оценки выберите «Допущение»; она не станет фактом поставщика.</p></header>
    <details className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm" aria-label="Источники и полнота входов"><summary>Источники и полнота входов</summary>
      <p>Параметры объекта и расчёт потребного парка показаны в техническом результате со своими источниками. Здесь «Данные пользователя» — ваш ввод; «Допущение для сценария» — предлагаемое или изменённое вами число. Цена каталога и условия аренды остаются неподтверждёнными коммерческими условиями.</p>
      <p className="mt-2">Расчёт парка: {capacityRunId ? 'сохранён' : 'нужен расчёт'} · Труд: {groupCount('Труд').join('/')} · Покупка: {groupCount('Покупка').join('/')} · Аренда: {groupCount('RaaS').join('/')} · Визуализация: {groupCount('Визуализация').join('/')}. Полноту расчёта окончательно проверяет сервер.</p>
      <p className="mt-2">Общие затраты площадки вводятся один раз для этого сценария. Если вы рассчитали несколько зон отдельно, их NPV и парки нельзя суммировать без модели общих ресурсов и межзональных потоков.</p>
    </details>
    <details className="rounded-xl border p-4 text-sm" aria-label="Формулы и происхождение показателей"><summary>Как формируются показатели</summary>
      <p className="mt-1">Числа появляются только в новом сохранённом результате после проверки сервером. Раскройте нужную строку, чтобы увидеть формулу и происхождение.</p>
      <div className="mt-2 grid gap-2 md:grid-cols-2">{CALCULATION_RULES.map(([title, formula, origin]) =>
        <details key={title} className="rounded border p-2"><summary className="cursor-pointer font-semibold">{title}</summary>
          <p className="mt-2">{formula}</p><p className="mt-1 text-slate-600">Источник: {origin}</p></details>)}</div>
    </details>
    <details className="rounded-xl border border-blue-200 p-4 text-sm" aria-label="Обзор веток перед сохранением"><summary>Что уже можно рассчитать</summary>
      <div className="mt-2 grid gap-2 md:grid-cols-2">{readiness.branches.map((branch) => <div key={branch.key} className="rounded border p-2">
        <strong>{branch.label}: {branch.missing.length === 0 ? 'готово к проверке сервером' : readiness.missingConditions.some((condition) => branch.key === 'labour' ? condition.group === 'Труд' : ['purchase', 'raas'].includes(branch.key)) ? 'нужно подтвердить' : 'можно сохранить частично'}</strong>
        {branch.missing.length > 0 && <p>{branch.key === 'capacity' ? '' : `Нужно подтвердить или заполнить: ${branch.missing.filter((field) => !['labour', 'discount_inputs'].includes(field)).map((field) => CHECKS.find((item) => item[1] === field)?.[3] || FIELDS.find((item) => item[2] === field)?.[3] || field).join('; ')}.`}</p>}
      </div>)}</div>
      <p className="mt-2">2D/3D: {readiness.visualMissing.length ? 'нужны начало работы и часовой пояс' : 'входы готовы к проверке сервером'}. Итоговый статус определяет сохранённый серверный результат.</p>
      {!readiness.fullReady && <p className="mt-2 text-amber-900">Если сохранить частично, в PDF/ZIP разделы труда, покупки, RaaS или визуализации с недостающими входами будут помечены «не рассчитано»; NPV для этих веток не появится. Технический результат останется доступен.</p>}
    </details>
    <div className="grid gap-3 md:grid-cols-3" role="group" aria-label="Глубина расчёта экономики">
      {ECONOMICS_DEPTHS.map((level) => <button key={level.code} type="button" aria-pressed={values.calculationDepth === level.code}
        className={`rounded-xl border p-4 text-left ${values.calculationDepth === level.code ? 'border-lime-400 bg-teal-950 text-white' : ''}`}
        onClick={() => setValues((current) => ({ ...current, calculationDepth: level.code }))}>
        <strong className="block">{level.label}</strong><span className="block text-sm mt-2">{level.description}</span></button>)}
    </div>
    <section className="rounded-xl border border-lime-400 bg-teal-950 p-4 text-white text-sm" aria-label="Полный расчёт типового объекта">
      <button type="button" disabled={busy} className="rounded-xl bg-lime-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-50" onClick={() => {
        const proposed = applyTypicalObjectEconomics(values, FIELDS, capacityRequest?.process?.object_kind || capacityRequest?.object_kind ||
          (process?.process_code?.startsWith('airport_') ? 'AIRPORT' : process?.process_code?.startsWith('clinic_') ? 'CLINIC' : 'WAREHOUSE'), manualEstimate, process?.process_code);
        setValues(proposed); void submit(null, proposed);
      }}>Сделать полный расчет для типового объекта со всеми допущениями</button>
      <p className="mt-2">Кнопка заменит экономические входы авторскими допущениями и сразу сохранит новый расчёт. Это включает зарплаты новых специалистов, условную цену робота, сервис, батареи и состав аренды. Условия не являются ценами или нормативами организаторов. Числа и источники сохранятся в отчёте; их можно изменить.</p>
    </section>
    {['Труд', 'Покупка', 'RaaS', 'Визуализация'].filter((group) => ECONOMICS_DEPTHS.findIndex((level) => level.groups.includes(group)) <= depthIndex(values.calculationDepth)).map((group) => <details open key={group} aria-label={group} className="rounded-xl border p-4">
      <summary className="font-semibold cursor-pointer">{group}</summary>
      {group === 'Труд' && <div className="mt-3 rounded border border-blue-300 p-3 text-sm space-y-3" aria-label="Покрытие новых функций после расчёта парка">
        <details><summary>Как определена потребность в новых функциях</summary><p>Парк: {fleet ?? 'нет данных'} роботов. Посты управления рассчитываются по числу роботов; штат — по постам, сменам и ротации. Техник может быть дневным, сменным или у поставщика. {staffingPreview.PURCHASE ? `На текущем вводе: диспетчеры ${staffingPreview.PURCHASE.control_required}, техники ${staffingPreview.PURCHASE.technicians_required}, перевод на пульт ${staffingPreview.PURCHASE.control_transferred}.` : 'Точное распределение будет показано после сохранения расчёта.'}</p></details>
        <div className="grid gap-2 md:grid-cols-3"><label>Роботов на пост<input type="number" min="0.01" step="any" value={values.robotsPerControlPost} onChange={set('robotsPerControlPost')} /></label><label>Роботов на дневного техника<input type="number" min="0.01" step="any" value={values.robotsPerDayTechnician} onChange={set('robotsPerDayTechnician')} /></label><label>Коэффициент ротации<input type="number" min="1" step="any" value={values.rotationFactor} onChange={set('rotationFactor')} /></label></div>
        <label>Присутствие техника<select value={values.technicianPresence} onChange={set('technicianPresence')}><option value="DAY_WORKLOAD">Дневная нагрузка</option><option value="EACH_SHIFT">В каждой смене</option><option value="VENDOR">У поставщика</option></select></label>
        <label>Доля роботизируемой работы роли, 0–1<input type="number" min="0" max="1" step="any" value={values.robotizableShare} onChange={set('robotizableShare')} /></label>
        <label>Какие ручные операции остаются<input type="text" value={values.residualOperations} onChange={set('residualOperations')} /></label>
        <p>Численность «сейчас» ниже описывает только исходный штат. Выберите, кто покроет новую функцию; перевод сохраняет человека в штате и уменьшает высвобождение.</p>
        <label className="block">Пульт<select id="economics-staffing-control" className="block w-full border rounded p-2" value={values.controlMode} onChange={set('controlMode')}><option value="">Выберите покрытие</option><option value="TRANSFER">Перевод из заменяемой роли</option><option value="HIRE">Отдельный найм</option><option value="EXISTING">Существующая функция</option></select></label>
        <label className="block">Техподдержка при покупке<select id="economics-staffing-purchase" className="block w-full border rounded p-2" value={values.technicianPurchaseMode} onChange={set('technicianPurchaseMode')}><option value="">Выберите покрытие</option><option value="TRANSFER">Перевод квалифицированного сотрудника</option><option value="HIRE">Отдельный найм</option><option value="EXISTING">Существующая функция</option><option value="CONTRACTOR">Подрядчик</option></select></label>
        {depthIndex(values.calculationDepth) >= 2 && <label className="block">Техподдержка при RaaS<select id="economics-staffing-raas" className="block w-full border rounded p-2" value={values.technicianRaasMode} onChange={set('technicianRaasMode')}><option value="">Выберите покрытие</option><option value="TRANSFER">Перевод квалифицированного сотрудника</option><option value="HIRE">Отдельный найм</option><option value="EXISTING">Существующая функция</option><option value="CONTRACTOR">Подрядчик</option><option value="VENDOR">Поставщик, включено в RaaS</option></select></label>}
        {(values.technicianPurchaseMode === 'TRANSFER' || values.technicianRaasMode === 'TRANSFER') && <label className="flex gap-2"><input type="checkbox" checked={values.qualifiedTechTransfer} onChange={set('qualifiedTechTransfer')} />Подтверждаю квалификацию переводимого сотрудника для техподдержки</label>}
        <p>Зарплата или стоимость услуги запрашивается ниже только для непокрытой функции. Неизвестная стоимость даёт частичный результат; выбор и источник сохраняются в новом run.</p>
      </div>}
      {group === 'Труд' && roleRefs.length > 1 && <label className="block mt-3 text-sm">Основная роль процесса
        <select value={values.primaryRoleId} onChange={(event) => setValues((current) => changeManualProductivityRole(current, event.target.value))} className="w-full border rounded p-2"><option value="">Неизвестно</option>{roleRefs.map((id, index) => <option key={id} value={id}>Роль {index + 1}</option>)}</select>
        <small>Для сравнения труда; источник — введённые роли процесса.</small></label>}
      {group === 'Труд' && <div className="mt-3 rounded border border-teal-300 p-3 text-sm" aria-label="Оценка ручной выработки">
        <strong>Выработка одного сотрудника {roleLabel} в процессе «{processLabel}»</strong>
        <p>Объём: {process?.demand?.normalized_value ?? 'неизвестно'} {process?.demand?.unit || 'ед./сутки'}; смен: {process?.schedule?.shifts_per_day?.normalized_value ?? 'неизвестно'}; длительность смены: {process?.schedule?.shift_hours?.normalized_value ?? 'неизвестно'} ч; плечо в одну сторону: {process?.route_distance?.normalized_value ?? 'не применяется'} м. Показатель определяет F08/F09, потребность людей и экономию ФОТ только выбранной роли.</p>
        {manualEstimate?.status === 'ESTIMATE' && <p className="mt-2">Оценка по действующему реестру F08: <strong title={manualEstimate.value}>≈ {estimateShown} {manualEstimate.unit}</strong>. {manualEstimate.formula}. {process?.scope === 'CLEANING_AREA'
          ? `Механизированная база ${manualEstimate.inputs.mechanized_rate_m2_h} м²/ч, полезное время ${manualEstimate.inputs.useful_time_share}.`
          : `Скорость человека ${manualEstimate.inputs.manual_speed_m_s ?? 'н/п'} м/с, обмен ${manualEstimate.inputs.manual_exchange_s ?? 'н/п'} с, полезное время ${manualEstimate.inputs.useful_time_share ?? 'н/п'}, единиц за рейс ${manualEstimate.inputs.units_per_trip ?? 'н/п'}.`} Источники: {manualEstimate.source_refs.join(', ')}. Это допущение, не замер на объекте.</p>}
        {manualEstimate?.status === 'ESTIMATE' && <button type="button" className="secondary-action mt-2" onClick={() => setValues((current) => applyManualProductivityEstimate(current, manualEstimate))}>Взять оценку как допущение и подтвердить ниже</button>}
        {manualEstimate?.status === 'UNSUPPORTED' && <p className="mt-2 text-amber-800">Для этого процесса нет утверждённой оценки ручной выработки. Введите измеренную норму; расчёт без неё останется частичным.</p>}
        {process?.scope === 'CLEANING_AREA' && <p className="mt-2">Для уборки укажите ручную выработку за смену; оценка реестра доступна как предварительное допущение.</p>}
      </div>}
      {group === 'Визуализация' && <div className="mt-2 rounded border p-3 text-sm">
        <p>Модельное начало: понедельник, {String(Math.floor(Number(values.startSeconds) / 3600)).padStart(2, '0')}:{String(Math.floor(Number(values.startSeconds) % 3600 / 60)).padStart(2, '0')} местного времени. Часовой пояс сохраняется в новом сценарии.</p>
        <label className="mt-2 block">Часовой пояс<select id="economics-timezone" value={values.timezone} onChange={set('timezone')} className="block w-full border rounded p-2"><option value="">Выберите часовой пояс</option>{timezoneChoices(values.timezone).map((zone) => <option key={zone} value={zone}>{zone.replaceAll('_', ' ')}</option>)}</select></label>
        <details className="mt-2"><summary>Детальная настройка модельного времени</summary><label className="mt-2 block">Начало смены · местное время<input id="economics-start_seconds_from_midnight" type="time" value={`${String(Math.floor(Number(values.startSeconds) / 3600)).padStart(2, '0')}:${String(Math.floor(Number(values.startSeconds) % 3600 / 60)).padStart(2, '0')}`} onChange={(event) => { const [h, m] = event.target.value.split(':').map(Number); setValues((current) => ({ ...current, startSeconds: String(h * 3600 + m * 60) })); }} className="block border rounded p-2" /></label><p>График смен из процесса сохраняется. Здесь задаётся только местное начало.</p></details>
      </div>}
      {group !== 'Визуализация' && <div className="mt-2 grid gap-3 md:grid-cols-3">{FIELDS.filter((field) => field[0] === group && visibleField(field)).map(([, key, server, label, unit, why, source]) => {
        const fieldIssues = issues.filter((item) => item.field === server);
        const staffingField = ['control_transfer_monthly_supplement_gross', 'technician_transfer_monthly_supplement_gross', 'technician_contractor_annual_gross'].includes(server);
        const displayLabel = key === 'manualUnitsPerShift' ? `Выработка одного сотрудника ${roleLabel} в процессе «${processLabel}»` : label;
        return <div key={key} className="block rounded border border-slate-500/40 p-3 text-sm">
          <strong className="block">{displayLabel} <span className="font-normal">· {unit}</span></strong>

          <input id={`economics-${server}`} type="text" inputMode="decimal" aria-label={displayLabel} value={values[key]} onChange={(event) => setValues((current) => editEconomicsField(current, key, server, event.target.value, { enableTemplate: demoEligible }))} className="w-full border rounded p-2 mt-2" placeholder="Неизвестно — оставьте пустым" aria-invalid={fieldIssues.some((item) => !['MISSING_INPUT', 'RANGE_ONLY'].includes(item.code))} />
          <details className="mt-2"><summary className="text-xs cursor-pointer">Источник и допущения</summary><small className="block mt-1">{why} Возможный источник: {source}. {['Покупка', 'RaaS'].includes(group) ? 'Коммерческое условие требует отдельной проверки.' : ''}</small>
          {!staffingField && <select value={values.sources[server] || 'USER'} onChange={(event) => setValues((current) => event.target.value === 'USER'
            ? chooseUserField(current, key, server) : proposeDemoField(current, key, server, { enableTemplate: demoEligible }))} aria-label={`Тип источника: ${label}`} className="w-full border rounded p-2 mt-1">
            <option value="USER">Данные пользователя</option><option value="ASSUMPTION">Допущение для сценария</option>
          </select>}
          {values.sources[server] === 'ASSUMPTION' && <div className="mt-2 rounded bg-amber-50 p-2 text-xs">
            {demoEligible && WAREHOUSE_ECONOMICS_DEMO.fields[server] ? <p>Предложение для «{fieldPresentation(server).label}» от {WAREHOUSE_ECONOMICS_DEMO.published_on}: {WAREHOUSE_ECONOMICS_DEMO.fields[server].value} {WAREHOUSE_ECONOMICS_DEMO.fields[server].unit}. {WAREHOUSE_ECONOMICS_DEMO.fields[server].rationale}. Источник: {WAREHOUSE_ECONOMICS_DEMO.source}.</p>
              : <p>Для этого поля нет шаблона. Введите число вручную и подтвердите его как ваше сценарное допущение.</p>}
            {values[key] !== '' && values.assumptions[server] && <label className="mt-1 flex gap-2"><input type="checkbox" checked={values.assumptions[server].confirmed === true} onChange={(event) => setValues((current) => confirmEconomicsAssumption(current, server, event.target.checked))} />Подтверждаю число {values[key]} для этого сценария</label>}
            {values[key] !== '' && !values.assumptions[server] && <p>Нужно ввести и подтвердить число.</p>}
          </div>}
          </details>
          {fieldIssues.map((item, index) => <small key={index} className={`block mt-1 ${['MISSING_INPUT', 'RANGE_ONLY'].includes(item.code) ? 'text-amber-900' : 'text-red-700'}`} role="status">{item.message} {item.next_step}</small>)}
        </div>;
      })}</div>}
      {group === 'Покупка' && <label className="block mt-3 text-sm">Дата оценки · дата<input id="economics-evaluation_date" type="date" value={values.evaluationDate} onChange={set('evaluationDate')} className="w-full border rounded p-2" /><small>Для привязки цен; источник — дата оценки проекта.</small></label>}
      {group === 'Покупка' && <div className="mt-3 rounded border p-3 text-sm"><label>Внедрение<select value={values.implementationMode} onChange={set('implementationMode')}><option value="FIXED">Сумма на проект</option><option value="PERCENT">% стоимости оборудования</option></select></label>{values.implementationMode === 'PERCENT' && <label>Процент внедрения<input type="number" min="0" max="100" step="any" value={values.implementationPercent} onChange={set('implementationPercent')} /></label>}<p>Сервер применяет процент к цене робота × сохранённый парк. Общая инфраструктура вводится отдельно.</p></div>}
      {group === 'Покупка' && depthIndex(values.calculationDepth) >= 2 && <div className="mt-3 rounded border p-3 text-sm"><strong>Уточнить цену одного робота</strong><p>Оставьте пустым для цены сохранённой позиции каталога. Изменение создаст новый экономический run; каталог и прежний расчёт останутся прежними.</p>
        <label className="mt-2 block">Цена, ₽ gross<input id="economics-purchase_price_override_gross" type="text" inputMode="decimal" value={values.purchasePriceOverride} onChange={set('purchasePriceOverride')} className="block w-full border rounded p-2" placeholder="Цена каталога без изменения" /></label>
        <label className="mt-2 block">Источник новой цены<input id="economics-purchase_price_source" type="text" value={values.purchasePriceSource} onChange={set('purchasePriceSource')} className="block w-full border rounded p-2" placeholder="Документ и дата либо пользовательское допущение" /></label>
        <p>Источник сохраняется как условие пользователя, а не подтверждение поставщика.</p></div>}
      {group === 'RaaS' && <label className="block mt-3 text-sm">Кто оплачивает инфраструктуру<select id="economics-raas_infrastructure_owner" value={values.raasInfrastructureOwner} onChange={set('raasInfrastructureOwner')} className="w-full border rounded p-2"><option value="">Неизвестно</option><option value="VENDOR">Поставщик</option><option value="CUSTOMER">Заказчик</option></select><small>Для состава затрат; источник — договор или допущение.</small></label>}
      {group === 'RaaS' && <div className="mt-3 rounded border p-3 text-sm"><label>Тариф RaaS<select value={values.raasMode} onChange={set('raasMode')}><option value="FIXED">₽/робот/месяц</option><option value="PERCENT">% цены робота в месяц</option></select></label>{values.raasMode === 'PERCENT' && <label>Месячный процент<input type="number" min="0" max="100" step="any" value={values.raasPercentMonthly} onChange={set('raasPercentMonthly')} /></label>}<p>Процент — месячный тариф услуги, не ставка кредита. Денежную сумму рассчитывает сервер.</p></div>}
    </details>)}
    <section className="rounded-xl border border-amber-300 p-4 text-sm" aria-label="Пять условий экономического сценария">
      <h3 className="font-semibold">Условия выбранного уровня</h3>
      <p>Каждое подтверждение относится только к этому сценарию и не подтверждает условия поставщика. Отметьте условия для собственного ввода. Кнопка типового объекта принимает их как сценарные допущения.</p>
      {CHECKS.filter(([group]) => group === 'Труд' || group === 'Покупка' && depthIndex(values.calculationDepth) >= 1 || group === 'RaaS' && depthIndex(values.calculationDepth) >= 2).map(([, key, server, label]) => <label key={key} className="mt-3 flex gap-2 rounded border p-2"><input id={`economics-condition-${key}`} type="checkbox" checked={values[key]} onChange={set(key)} /><span>{label}<small className="block">{ECONOMICS_CONDITIONS.find((item) => item.key === key)?.consequence}</small>{issues.some((item) => item.field === server) && <small className="block text-red-700">Нужно для этой ветки.</small>}</span></label>)}
    </section>
    <p className="text-sm">Пригодность на объекте и закупочная готовность проверяются отдельно. Этот расчёт не подтверждает поставщика и не даёт рекомендации к закупке.</p>
    {error && <p className="text-red-700" role="alert">{error}</p>}
    <div className="flex flex-wrap gap-3"><button type="button" disabled={busy} onClick={submit} className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-50">{busy ? 'Сохраняем…' : 'Рассчитать и сохранить выбранный уровень'}</button>
      {values.calculationDepth === 'FULL' && !readiness.fullReady && <button type="button" className="secondary-action" onClick={goToMissing}>Показать недостающие входы</button>}</div>
    <p className="text-sm">Каждый уровень сохраняется и скачивается. Глубина описывает состав выбранных входов; фактически рассчитанные ветки и неизвестные данные отдельно указаны в результате.</p>
  </form>;
}
