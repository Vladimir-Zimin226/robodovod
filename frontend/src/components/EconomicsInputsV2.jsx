import { cloneElement, useEffect, useState } from 'react';
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
import { fieldPresentation, humanizePresentation, presentationValue } from '../presentation';
import { formatDecimal, formatPercent } from '../displayNumber';
import { MODEL_START_SECONDS, modelTimezone, timezoneChoices } from '../simulationDefaults';
import { workbookEconomics } from '../projectWorkbook';
import { PROCESS_DEFINITIONS } from '../processRoleIntakeV2';
import { ECONOMICS_DEPTHS, depthIndex, valuesAtDepth } from '../economicsDepth';
import { roleLabel as roleName } from '../roleLabels';
import { buildRoleWorkProfiles, primaryWorkEvidence, PRIMARY_ROLE_BASIS, ZERO_ROLE_BASIS, ZERO_ROLE_RESIDUAL } from '../roleWorkProfiles';
import { applyRoleWorkScenario } from '../roleWorkScenarioAssumptions';

const API = import.meta.env.VITE_API_URL || '';
const today = () => new Date().toISOString().slice(0, 10);
const FIELDS = [
  ['Труд', 'manualUnitsPerShift', 'manual_units_per_shift', 'Выработка одного сотрудника', 'ед./смену', 'Для потребности в персонале и экономии оплаты труда; например 100.', 'Замер или подтверждённая оценка'],
  ['Труд', 'controlHeadcount', 'control_headcount', 'Диспетчеры сейчас', 'чел.', 'Для добавочной численности; например 0.', 'Штатное расписание'],
  ['Труд', 'controlMonthlyGross', 'control_monthly_gross', 'Диспетчер · стоимость для компании', '₽/чел./мес.', 'Включая страховые взносы при выбранной базе.', 'ФОТ'],
  ['Труд', 'technicianHeadcount', 'technician_headcount', 'Техники сейчас', 'чел.', 'Для дополнительной техподдержки; например 0.', 'Штатное расписание'],
  ['Труд', 'technicianMonthlyGross', 'technician_monthly_gross', 'Техник · стоимость для компании', '₽/чел./мес.', 'Включая страховые взносы при выбранной базе.', 'ФОТ'],
  ['Труд', 'controlTransferSupplement', 'control_transfer_monthly_supplement_gross', 'Доплата переведённому диспетчеру', '₽/чел./мес., gross', 'Введите подтверждённый ноль, если доплаты нет.', 'Кадровое решение'],
  ['Труд', 'techTransferSupplement', 'technician_transfer_monthly_supplement_gross', 'Доплата переведённому технику', '₽/чел./мес., gross', 'Введите подтверждённый ноль, если доплаты нет.', 'Кадровое решение'],
  ['Труд', 'technicianContractorAnnual', 'technician_contractor_annual_gross', 'Техподдержка подрядчика', '₽/техник/год, gross', 'Стоимость только непокрытой функции.', 'Договор или допущение'],
  ['Покупка', 'implementationCost', 'implementation_cost_total_gross', 'Прочие работы по внедрению', '₽ всего, gross', 'Только работы сверх доставки, пусконаладки и интеграции. Введите 0, если прочих работ точно нет; пустое поле остаётся неизвестным.', 'Смета или допущение'],
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
  ['Труд', 'grossConfirm', 'role_salaries_confirmed_as_monthly_gross', 'Подтверждаю выбранную базу месячных расходов для всех ролей.'],
  ['Покупка', 'currencyConfirm', 'organizer_price_currency_rub_confirmed', 'Для сценария трактую цену организаторов как рубли. Это не оферта поставщика.'],
  ['Покупка', 'initialBatteryConfirm', 'initial_battery_in_robot_price_confirmed', 'Для сценария начальная батарея включена в цену робота.'],
  ['Покупка', 'batteryServiceConfirm', 'battery_replacements_in_service_confirmed', 'Для сценария замены батареи включены в сервис.'],
  ['RaaS', 'raasScopeConfirm', 'raas_vendor_scope_confirmed', 'Для сценария RaaS включает оборудование, батареи, зарядку, обслуживание, ПО и интеграцию. Это не факт поставщика.'],
];
const CALCULATION_RULES = [
  ['Труд', 'Прямая годовая стоимость = месячная стоимость работодателя × 12. Для старого ввода начисленной зарплаты расходы работодателя добавляются по допущению реестра.', 'База зарплаты сохраняется с расчётом. Высвобождение ограничено парком, ролью и пультом.'],
  ['Покупка', 'Разовые затраты = оборудование + подтверждённые статьи внедрения и площадки + резерв. Амортизируемая база исключает резерв.', 'Цена позиции каталога или указанная вами цена; затраты и гарантия из формы; резерв и отдельные нормы из действующего реестра.'],
  ['RaaS', 'Затраты заказчика = его инфраструктура + годовые расходы заказчика + платежи по выбранному тарифу.', 'Тариф, срок и владелец инфраструктуры из формы; состав услуги требует отдельного подтверждения и не является фактом поставщика.'],
  ['Денежный результат', 'NPV проекта = NPV сценария − NPV базы; ROI покупки = (эффект − CAPEX) / CAPEX × 100 %. Для RaaS из эффекта вычитается CAPEX инфраструктуры клиента, результат делится на TCO услуги и умножается на 100 %.', 'Годовые потоки строит сервер из сохранённых труда, парка и затрат. При нулевом CAPEX ROI не определён.'],
  ['Налог', 'Основной денежный маршрут рассчитывается до налога на прибыль. НДС не пересчитывается единой ставкой: денежная база использует gross цену по принятому условию сценария.', 'Налоговый режим организации в этой форме неизвестен; иллюстративная налоговая ветка не включается в основной NPV.'],
];
const FINANCIAL_FACTS = [
  ['warranty_years', 'Гарантия', 'лет'], ['annual_service_rub', 'Сервис', '₽/год'],
  ['average_power_w', 'Средняя мощность', 'Вт'], ['max_power_w', 'Максимальная мощность', 'Вт'],
  ['battery_kwh', 'Батарея', 'кВт·ч'], ['charger_power_kw', 'Зарядка', 'кВт'],
];
const IMPLEMENTATION_LINES = [['DELIVERY', 'Доставка'], ['COMMISSIONING', 'Пусконаладка'], ['INTEGRATION', 'Интеграция']];
const blankImplementationLines = () => Object.fromEntries(IMPLEMENTATION_LINES.map(([category]) =>
  [category, { status: 'UNKNOWN', amount: '', source_ref: '', explanation: '', included_in: null }]));
const defaults = { calculationDepth: 'BASIC', evaluationDate: today(), primaryRoleId: '', raasInfrastructureOwner: '', timezone: '', purchasePriceOverride: '', purchasePriceSource: '', salaryBasis: 'EMPLOYER_COST', energyPowerBasis: 'AVERAGE', chargerPowerKw: '', chargingSimultaneityFraction: '',
  implementationMode: 'FIXED', implementationPercent: '', raasMode: 'FIXED', raasPercentMonthly: '',
  robotsPerControlPost: '', robotsPerDayTechnician: '', rotationFactor: '', technicianPresence: 'DAY_WORKLOAD', robotizableShare: '', residualOperations: '',
  controlMode: '', technicianPurchaseMode: '', technicianRaasMode: '', qualifiedTechTransfer: false,
  sources: {}, assumptions: {}, userValues: {}, roleWorkProfiles: {}, implementationLines: blankImplementationLines() };
function restored(capacityRunId, input, project) {
  const values = { ...defaults, calculationDepth: input?.calculation_depth || (input ? 'FULL' : 'BASIC'), capacityRunId, sources: { ...(input?.field_sources || {}) },
    assumptions: { ...(input?.assumption_evidence || {}) }, userValues: {} };
  FIELDS.forEach(([, key, server]) => { values[key] = String(input?.[server] ?? ''); });
  values.purchasePriceOverride = String(input?.purchase_price_override_gross ?? '');
  values.purchasePriceSource = input?.purchase_price_source || '';
  CHECKS.forEach(([, key, server]) => { values[key] = input?.[server] === true; });
  values.salaryBasis = input?.salary_basis || (input ? 'GROSS' : 'EMPLOYER_COST');
  values.energyPowerBasis = input?.energy_power_basis || 'AVERAGE';
  values.chargerPowerKw = String(input?.charger_power_kw ?? '');
  values.chargingSimultaneityFraction = String(input?.charging_simultaneity_fraction ?? '');
  values.roleWorkProfiles = Object.fromEntries((input?.role_work_profiles || []).map((profile) =>
    [profile.role_id, { fraction: String(profile.robotizable_fraction), manual: String(profile.manual_units_per_shift ?? ''),
      ...(profile.process_allocation_fraction != null ? { allocationFraction: String(profile.process_allocation_fraction) } : {}),
      residual: profile.residual_operations, basis: profile.basis, source: profile.source, confirmed: profile.confirmed === true }]));
  if (input) Object.assign(values, { evaluationDate: input.evaluation_date || '', primaryRoleId: input.primary_role_id || '',
    raasInfrastructureOwner: input.raas_infrastructure_owner || '', timezone: Object.hasOwn(input, 'timezone') ? input.timezone : modelTimezone(project),
    startSeconds: input.start_seconds_from_midnight == null ? String(MODEL_START_SECONDS) : String(input.start_seconds_from_midnight) });
  if (['economics-explicit-inputs-v5', 'economics-explicit-inputs-v6', 'economics-explicit-inputs-v7'].includes(input?.schema_version)) Object.assign(values, {
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
  if (['economics-explicit-inputs-v6', 'economics-explicit-inputs-v7'].includes(input?.schema_version)) Object.assign(values, {
    implementationMode: input.implementation_mode || 'FIXED', implementationPercent: input.implementation_percent || '',
    raasMode: input.raas_mode || 'FIXED', raasPercentMonthly: input.raas_percent_monthly || '',
    robotsPerControlPost: input.staffing_policy?.robots_per_control_post || '',
    robotsPerDayTechnician: input.staffing_policy?.robots_per_day_technician || '',
    rotationFactor: input.staffing_policy?.rotation_factor || '',
    technicianPresence: input.staffing_policy?.technician_presence || 'DAY_WORKLOAD',
    robotizableShare: input.work_share?.fraction || '', residualOperations: input.work_share?.residual_operations || '',
  });
  if (input?.schema_version === 'economics-explicit-inputs-v7') values.implementationLines = Object.fromEntries(
    IMPLEMENTATION_LINES.map(([category]) => [category, {
      ...blankImplementationLines()[category], ...(input.implementation_lines?.[category] || {}),
      amount: String(input.implementation_lines?.[category]?.amount ?? ''),
    }]));
  if (!input) Object.assign(values, { startSeconds: String(MODEL_START_SECONDS), timezone: modelTimezone(project) });
  return values;
}

function LabourField({ id, label, hint, full = false, children }) {
  return <div className={`labour-field${full ? ' labour-field-full' : ''}`}>
    <label htmlFor={id}>{label}</label>
    {cloneElement(children, { id, 'aria-describedby': `${id}-hint ${id}-message` })}
    <small id={`${id}-hint`}>{hint}</small><small id={`${id}-message`} className="labour-field-message" aria-live="polite" />
  </div>;
}
export default function EconomicsInputsV2({ capacityRequest, capacityResult, capacityRunId, project, onComplete, initialInput, savedResult, sourceRunId, initialDepth = 'BASIC' }) {
  const [values, setValues] = useState(() => ({ ...restored(capacityRunId, initialInput || workbookEconomics(project?.profile?.file_intake_v2), project),
    ...(initialInput ? {} : { calculationDepth: initialDepth }) }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [manualEstimate, setManualEstimate] = useState(null);
  const [selectedPosition, setSelectedPosition] = useState(null);
  useEffect(() => {
    const positionId = capacityRequest?.position_id;
    if (!positionId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/v2/capacity-catalog/positions/${encodeURIComponent(positionId)}`, { credentials: 'include', signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then((result) => setSelectedPosition(result))
      .catch((reason) => { if (reason.name !== 'AbortError') setSelectedPosition(null); });
    return () => controller.abort();
  }, [capacityRequest?.position_id]);
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
  const unconfirmPrimary = (draft, current) => {
    const roleId = current.primaryRoleId || (capacityRequest?.process?.role_refs?.length === 1 ? capacityRequest.process.role_refs[0] : null);
    return roleId ? { ...draft, roleWorkProfiles: { ...draft.roleWorkProfiles,
      [roleId]: { ...draft.roleWorkProfiles?.[roleId], confirmed: false } } } : draft;
  };
  const set = (key) => (event) => setValues((current) => {
    const next = { ...current, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value };
    return ['robotizableShare', 'manualUnitsPerShift', 'residualOperations'].includes(key)
      ? unconfirmPrimary(next, current) : next;
  });
  const setRoleWork = (roleId, field) => (event) => setValues((current) => ({ ...current,
    roleWorkProfiles: { ...current.roleWorkProfiles,
      [roleId]: { ...current.roleWorkProfiles[roleId], [field]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
        ...(field === 'confirmed' ? {} : { confirmed: false }) } } }));
  const setImplementationLine = (category, key, value) => setValues((current) => ({ ...current,
    implementationLines: { ...current.implementationLines,
      [category]: { ...current.implementationLines[category], [key]: value,
        ...(key === 'status' ? { amount: value === 'EXPLICIT_ZERO' ? '0' : '',
          included_in: value === 'INCLUDED' ? 'implementation_cost_total_gross' : null } : {}) } } }));
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
    if (key === 'technicianMonthlyGross') return Number(values.technicianHeadcount) > 0 || (values.technicianPurchaseMode === 'HIRE' || values.technicianRaasMode === 'HIRE') && Number(fleet) > 0;
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
      if (depthIndex(prepared.calculationDepth) >= 1) prepared.implementationLines = Object.fromEntries(
        IMPLEMENTATION_LINES.map(([category]) => {
          const line = prepared.implementationLines[category];
          return [category, { ...line, amount: ['USER_ESTIMATE', 'USER_MEASURED', 'POLICY_ASSUMPTION', 'EXPLICIT_ZERO'].includes(line.status) ? line.amount : null,
            included_in: line.status === 'INCLUDED' ? 'implementation_cost_total_gross' : null }];
        }));
      else prepared.implementationLines = blankImplementationLines();
      const policyDate = today();
      const primaryRoleId = prepared.primaryRoleId || (capacityRequest?.process?.role_refs?.length === 1
        ? capacityRequest.process.role_refs[0] : null);
      const roleWorkProfiles = buildRoleWorkProfiles(prepared, capacityRequest?.process?.role_refs || [], primaryRoleId);
      const primaryEvidence = primaryWorkEvidence(prepared, primaryRoleId);
      const body = buildPartialEconomicsRunRequest({ values: { ...prepared, capacityRunId,
        roleWorkProfiles,
        staffingPolicy: prepared.robotsPerControlPost && prepared.robotsPerDayTechnician && prepared.rotationFactor ? {
          schema_version: 'staffing-policy-v2', robots_per_control_post: prepared.robotsPerControlPost,
          robots_per_day_technician: prepared.robotsPerDayTechnician, rotation_factor: prepared.rotationFactor,
          technician_presence: prepared.technicianPresence, source: 'ASSUMPTION',
          basis: 'Принято пользователем для проектного расчёта; проверить нагрузку на объекте', date: policyDate, confirmed: true,
        } : null,
        workShare: prepared.robotizableShare !== '' && prepared.residualOperations ? {
          schema_version: 'robotizable-work-share-v1', fraction: prepared.robotizableShare,
          residual_operations: prepared.residualOperations, source: primaryEvidence.source,
          basis: primaryEvidence.basis, date: policyDate, confirmed: primaryEvidence.confirmed,
        } : null }, capacityRequest, project, scenario, sourceRunId, projectPolicyMode: true });
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
  const processLabel = PROCESS_DEFINITIONS.find((item) => item.code === process?.process_code)?.label || 'выбранном процессе';
  const selectedRoleId = values.primaryRoleId || (roleRefs.length === 1 ? roleRefs[0] : null);
  const selectedRole = capacityRequest?.role_pool?.roles?.find((item) => item.role_id === selectedRoleId);
  const roleLabel = selectedRole ? roleName(selectedRole.role_code).toLowerCase() : 'выбранной роли';
  const estimateShown = manualEstimate?.status === 'ESTIMATE'
    ? formatDecimal(manualEstimate.value) : null;
  return <form className="economics-inputs-v2 mx-auto my-6 max-w-6xl rounded-2xl border p-5 shadow-sm space-y-5" onSubmit={(event) => event.preventDefault()} noValidate aria-label="Расчёт экономики роботизации">
    <header><span className="simple-step-eyebrow">ШАГ 4 ИЗ 5 · ДЕНЬГИ</span><h2 className="text-xl font-semibold">Сколько будет стоить решение?</h2>
      <p className="mt-1 text-sm">Выберите глубину оценки, затем откройте нужный блок затрат. Пустое поле означает «неизвестно», а ноль требует подтверждения.</p></header>
    <details className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm" aria-label="Источники и полнота входов"><summary>Источники и полнота входов</summary>
      <p>Параметры объекта и расчёт потребного парка показаны в техническом результате со своими источниками. Здесь «Данные пользователя» — ваш ввод; «Допущение для сценария» — предлагаемое или изменённое вами число. Цена каталога и условия аренды остаются неподтверждёнными коммерческими условиями.</p>
      <p className="mt-2">Расчёт парка: {capacityRunId ? 'сохранён' : 'нужен расчёт'} · Труд: {groupCount('Труд').join('/')} · Покупка: {groupCount('Покупка').join('/')} · Аренда: {groupCount('RaaS').join('/')} · Визуализация: {groupCount('Визуализация').join('/')}. Полноту расчёта окончательно проверяет сервер.</p>
      <p className="mt-2">Общие затраты площадки вводятся один раз для этого сценария. Если вы рассчитали несколько зон отдельно, их NPV и парки нельзя суммировать без модели общих ресурсов и межзональных потоков.</p>
    </details>
    <details className="rounded-xl border p-4 text-sm" aria-label="Формулы и происхождение показателей"><summary>Как формируются показатели</summary>
      <p className="mt-1">Числа появляются только в новом сохранённом результате после проверки сервером. Раскройте нужную строку, чтобы увидеть формулу и происхождение.</p>
      <div className="mt-2 grid gap-2 md:grid-cols-2">{CALCULATION_RULES.map(([title, formula, origin]) =>
        <details key={title} className="rounded border p-2"><summary className="cursor-pointer font-semibold">{title}</summary>
          <p className="mt-2">{humanizePresentation(formula)}</p><p className="mt-1 text-slate-600">Источник: сохранённая методика расчёта. {humanizePresentation(origin)}</p></details>)}</div>
    </details>
    <details className="rounded-xl border border-blue-200 p-4 text-sm" aria-label="Обзор веток перед сохранением"><summary>Что уже можно рассчитать</summary>
      <div className="mt-2 grid gap-2 md:grid-cols-2">{readiness.branches.map((branch) => <div key={branch.key} className="rounded border p-2">
        <strong>{branch.label}: {branch.missing.length === 0 ? 'готово к проверке сервером' : readiness.missingConditions.some((condition) => branch.key === 'labour' ? condition.group === 'Труд' : ['purchase', 'raas'].includes(branch.key)) ? 'нужно подтвердить' : 'можно сохранить частично'}</strong>
        {branch.missing.length > 0 && <p>{branch.key === 'capacity' ? '' : `Нужно подтвердить или заполнить: ${branch.missing.filter((field) => !['labour', 'discount_inputs'].includes(field)).map((field) => CHECKS.find((item) => item[1] === field)?.[3] || FIELDS.find((item) => item[2] === field)?.[3] || fieldPresentation(field).label).join('; ')}.`}</p>}
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
    <div className="economics-cost-overview" aria-label="Три части экономики">
      <div><span>01</span><strong>Труд</strong><small>Что стоит ручная работа и какие функции останутся</small><b>{groupCount('Труд').join('/')} входов</b></div>
      <div><span>02</span><strong>Покупка</strong><small>Роботы, доставка, внедрение и эксплуатация</small><b>{depthIndex(values.calculationDepth) >= 1 ? `${groupCount('Покупка').join('/')} входов` : 'Следующий уровень'}</b></div>
      <div><span>03</span><strong>Аренда</strong><small>Ежемесячный тариф и условия поставщика</small><b>{depthIndex(values.calculationDepth) >= 2 ? `${groupCount('RaaS').join('/')} входов` : 'Полный уровень'}</b></div>
    </div>
    <section className="rounded-xl border border-lime-400 bg-teal-950 p-4 text-white text-sm" aria-label="Черновые допущения типового объекта">
      <button type="button" disabled={busy} className="rounded-xl bg-lime-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-50" onClick={() => {
        const proposed = applyRoleWorkScenario(applyTypicalObjectEconomics(values, FIELDS, capacityRequest?.process?.object_kind || capacityRequest?.object_kind ||
          (process?.process_code?.startsWith('airport_') ? 'AIRPORT' : process?.process_code?.startsWith('clinic_') ? 'CLINIC' : 'WAREHOUSE'), manualEstimate, process?.process_code,
          { catalogPriceAvailable: selectedPosition?.position?.purchase?.amount != null }), capacityRequest);
        const primaryRoleId = proposed.primaryRoleId || (capacityRequest?.process?.role_refs?.length === 1
          ? capacityRequest.process.role_refs[0] : null);
        setValues(primaryRoleId && !proposed.roleWorkProfiles?.[primaryRoleId] ? { ...proposed, roleWorkProfiles: { ...proposed.roleWorkProfiles,
          [primaryRoleId]: { ...proposed.roleWorkProfiles?.[primaryRoleId], source: 'ASSUMPTION',
            basis: PRIMARY_ROLE_BASIS, confirmed: false } } } : proposed);
      }}>Подставить черновые допущения</button>
      <p className="mt-2">Пример предложит часть расходов и условий как сценарные допущения. Доставку, пусконаладку и интеграцию подтвердите отдельно: без них покупка останется частичной. При доступной цене выбранной модели она сохранится как основа, иначе пример предложит условную цену; это не оферта поставщика.</p>
    </section>
    {['Труд', 'Покупка', 'RaaS', 'Визуализация'].filter((group) => ECONOMICS_DEPTHS.findIndex((level) => level.groups.includes(group)) <= depthIndex(values.calculationDepth)).map((group) => <details defaultOpen={group === 'Труд'} key={group} aria-label={group} className="economics-cost-section rounded-xl border p-4">
      <summary className="font-semibold cursor-pointer">{group === 'RaaS' ? 'Аренда' : group} <small> · {group === 'Визуализация' ? 'время и условия сцены' : `${groupCount(group).join('/')} входов`}</small></summary>
      {group === 'Покупка' && <div className="mt-3 rounded-xl border border-blue-300 bg-blue-50 p-4 text-sm">
        <strong>Смета выбранного решения</strong>
        <p>{selectedPosition?.position?.name || 'Выбранная модель загружается'} · {fleet ?? '—'} шт.</p>
        {selectedPosition?.position?.purchase?.amount != null
          ? <p>Цена позиции: {Number(selectedPosition.financial_facts?.price?.value || selectedPosition.position.purchase.amount).toLocaleString('ru-RU')} {selectedPosition.position.purchase.currency === 'RUB' ? '₽' : '(валюта не подтверждена)'} за робота. Она используется расчётом после подтверждения рублёвой базы, если ниже не задана другая цена. Источник: строка {selectedPosition.financial_facts?.price?.source_row_number || '—'} каталога {selectedPosition.catalog.code}{selectedPosition.financial_facts?.price?.observed_on ? ` от ${selectedPosition.financial_facts.price.observed_on}` : ''}; статус: {selectedPosition.position.purchase.price_status}.</p>
          : <p>Подтверждённой цены позиции нет. Для денежного результата понадобится предложение поставщика или явно принятое допущение.</p>}
        <div className="mt-2 grid gap-2 sm:grid-cols-2">{FINANCIAL_FACTS.map(([key, label, unit]) => {
          const fact = selectedPosition?.financial_facts?.[key];
          return <p key={key} className="rounded border bg-white p-2"><strong>{label}:</strong> {fact?.status === 'KNOWN' ? `${fact.value} ${unit}` : 'нет подтверждённого значения в активном каталоге'}{fact?.evidence_id && <small className="block">Источник: {fact.evidence_id}</small>}</p>;
        })}</div>
        <p>Паспортные характеристики модели и коммерческие условия поставки различаются. В этой версии каталога неизвестные сервис, гарантия и мощность не подставляются автоматически: тогда итог покажет недостающие данные.</p>
        <label className="mt-3 block">Как оценивать электроэнергию этой модели?
          <select className="mt-1 block w-full rounded border p-2" value={values.energyPowerBasis} onChange={set('energyPowerBasis')}>
            <option value="AVERAGE">Рабочая оценка по средней мощности</option>
            <option value="MAX_UPPER_BOUND">Осторожная верхняя граница по максимальной мощности</option>
          </select>
        </label>
        <p className="mt-1">В поле мощности ниже введите значение для выбранного режима. Максимальная паспортная мощность × время работы даёт верхнюю оценку кВт·ч, а не ожидаемый счёт. Пиковая нагрузка зарядки требует отдельной мощности зарядного устройства и числа одновременных зарядок.</p>
        <details className="mt-3 rounded border bg-white p-2"><summary>Уточнить пиковую нагрузку зарядки (необязательно)</summary>
          <div className="mt-2 grid gap-2 sm:grid-cols-2"><label>Мощность зарядного устройства, кВт<input type="number" min="0" step="any" value={values.chargerPowerKw} onChange={set('chargerPowerKw')} className="block w-full rounded border p-2" /></label>
            <label>Доля парка на зарядке одновременно, 0–1<input type="number" min="0" max="1" step="any" value={values.chargingSimultaneityFraction} onChange={set('chargingSimultaneityFraction')} className="block w-full rounded border p-2" /></label></div>
          <p>Оба значения нужны для оценки пика по этой модели: парк × мощность зарядки × доля одновременности. Пустые поля сохраняются как неизвестные.</p>
        </details>
      </div>}
      {group === 'Покупка' && <section className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm" aria-label="Статьи внедрения">
        <h3 className="font-semibold">Что входит в стоимость внедрения?</h3>
        <p>Цена робота из каталога может не включать доставку, пусконаладку и интеграцию. Для каждой статьи укажите сумму и источник либо объясните подтверждённый ноль. Пока статья неизвестна, NPV и окупаемость покупки не считаются.</p>
        <div className="mt-3 grid gap-3 md:grid-cols-3">{IMPLEMENTATION_LINES.map(([category, label]) => {
          const line = values.implementationLines[category];
          const lineIssues = issues.filter((item) => item.field === `implementation_lines.${category.toLowerCase()}`);
          return <div className="rounded border bg-white p-3" key={category}>
            <strong>{label}</strong>
            <label className="mt-2 block">Статус<select className="block w-full rounded border p-2" value={line.status} onChange={(event) => setImplementationLine(category, 'status', event.target.value)}>
              <option value="UNKNOWN">Неизвестно</option><option value="USER_ESTIMATE">Оценка по смете</option>
              <option value="USER_MEASURED">Подтверждённая сумма</option><option value="POLICY_ASSUMPTION">Моё допущение</option>
              <option value="EXPLICIT_ZERO">Подтверждённый ноль</option><option value="NOT_APPLICABLE">Не применяется</option>
              <option value="INCLUDED">Включено в прочие работы</option>
            </select></label>
            {['USER_ESTIMATE', 'USER_MEASURED', 'POLICY_ASSUMPTION'].includes(line.status) && <>
              <label className="mt-2 block">Сумма, ₽ gross<input className="block w-full rounded border p-2" type="text" inputMode="decimal" value={line.amount} onChange={(event) => setImplementationLine(category, 'amount', event.target.value)} placeholder="Например, 150000" /></label>
              <label className="mt-2 block">Источник суммы<input className="block w-full rounded border p-2" value={line.source_ref} onChange={(event) => setImplementationLine(category, 'source_ref', event.target.value)} placeholder="Смета и дата или моё допущение" /></label>
            </>}
            {['EXPLICIT_ZERO', 'NOT_APPLICABLE', 'INCLUDED', 'POLICY_ASSUMPTION'].includes(line.status) && <label className="mt-2 block">Основание<textarea className="block w-full rounded border p-2" rows="2" value={line.explanation} onChange={(event) => setImplementationLine(category, 'explanation', event.target.value)} placeholder="Почему выбран этот статус" /></label>}
            {line.status === 'INCLUDED' && <p>Укажите сумму в поле «Прочие работы по внедрению» ниже.</p>}
            {lineIssues.map((item, index) => <p key={index} className="mt-2 text-red-700" role="status">{item.message} {item.next_step}</p>)}
          </div>;
        })}</div>
      </section>}
      {group === 'Труд' && <div className="mt-3 rounded-xl border border-teal-300 bg-teal-50 p-4 text-sm space-y-3">
        <strong>1. Сколько сейчас стоит работа команды?</strong>
        <p>Численность и стоимость основных ролей уже введены на шаге «Объект». Здесь укажите выработку и сотрудников, которые будут сопровождать роботов.</p>
        <label className="block">Что означают месячные суммы для всех ролей?
          <select id="economics-salary-basis" className="mt-1 block w-full rounded border p-2" value={values.salaryBasis} onChange={set('salaryBasis')}>
            <option value="EMPLOYER_COST">Полные расходы компании, включая страховые взносы</option>
            <option value="GROSS">Начисленная зарплата без взносов работодателя (старые данные)</option>
          </select>
        </label>
        <p>При первом варианте страховые взносы второй раз не начисляются. НДФЛ отдельно к расходам компании не прибавляется. Для старого ввода выберите второй вариант и проверьте суммы в «Объекте».</p>
        <label className="flex gap-2 rounded border bg-white p-2"><input id="economics-condition-grossConfirm" type="checkbox" checked={values.grossConfirm} onChange={set('grossConfirm')} />Подтверждаю, что суммы всех ролей и этой формы указаны в выбранной базе за месяц на человека.</label>
      </div>}
      {group === 'Труд' && <div className="mt-3 rounded border border-blue-300 p-3 text-sm space-y-3" aria-label="Покрытие новых функций после расчёта парка">
        <strong>2. Как изменится работа после роботизации?</strong>
        <details><summary>Как определена потребность в новых функциях</summary><p>Парк: {fleet ?? 'нет данных'} роботов. Посты управления рассчитываются по числу роботов; штат — по постам, сменам и ротации. Техник может быть дневным, сменным или у поставщика. {staffingPreview.PURCHASE ? `На текущем вводе: диспетчеры ${staffingPreview.PURCHASE.control_required}, техники ${staffingPreview.PURCHASE.technicians_required}, перевод на пульт ${staffingPreview.PURCHASE.control_transferred}.` : 'Точное распределение будет показано после сохранения расчёта.'}</p></details>
        <details className="rounded border bg-white p-3"><summary>Уточнить нагрузку команды и долю работы робота</summary>
        <div className="labour-fields">
          <LabourField id="economics-robots-per-control" label="Роботов на пост" hint="Нагрузка одного поста управления, роботов."><input type="number" min="0.01" step="any" value={values.robotsPerControlPost} onChange={set('robotsPerControlPost')} /></LabourField>
          <LabourField id="economics-robots-per-technician" label="Роботов на дневного техника" hint="Нагрузка обслуживания, роботов."><input type="number" min="0.01" step="any" value={values.robotsPerDayTechnician} onChange={set('robotsPerDayTechnician')} /></LabourField>
          <LabourField id="economics-rotation" label="Коэффициент ротации" hint="Учитывает замены сотрудников в графике."><input type="number" min="1" step="any" value={values.rotationFactor} onChange={set('rotationFactor')} /></LabourField>
          <LabourField id="economics-technician-presence" label="Присутствие техника" hint="Основание для потребности в персонале."><select value={values.technicianPresence} onChange={set('technicianPresence')}><option value="DAY_WORKLOAD">Дневная нагрузка</option><option value="EACH_SHIFT">В каждой смене</option><option value="VENDOR">У поставщика</option></select></LabourField>
          <LabourField id="economics-work-share" label="Доля роботизируемой работы роли" hint={`Доля от 0 до 1. Текущий ввод: ${formatPercent(values.robotizableShare)}.`}><input type="number" min="0" max="1" step="any" value={values.robotizableShare} onChange={set('robotizableShare')} /></LabourField>
          <LabourField id="economics-residual-operations" label="Какие ручные операции остаются" hint="Эта работа сохраняется у сотрудников выбранной роли." full><textarea rows="3" value={values.residualOperations} onChange={set('residualOperations')} /></LabourField>
        </div>
        </details>
        <p>Численность «сейчас» ниже описывает только исходный штат. Выберите, кто покроет новую функцию; перевод сохраняет человека в штате и уменьшает высвобождение.</p>
        <label className="block">Пульт<select id="economics-staffing-control" className="block w-full border rounded p-2" value={values.controlMode} onChange={set('controlMode')}><option value="">Выберите покрытие</option><option value="TRANSFER">Перевод из заменяемой роли</option><option value="HIRE">Отдельный найм</option><option value="EXISTING">Существующая функция</option></select></label>
        <label className="block">Техподдержка при покупке<select id="economics-staffing-purchase" className="block w-full border rounded p-2" value={values.technicianPurchaseMode} onChange={set('technicianPurchaseMode')}><option value="">Выберите покрытие</option><option value="TRANSFER">Перевод квалифицированного сотрудника</option><option value="HIRE">Отдельный найм</option><option value="EXISTING">Существующая функция</option><option value="CONTRACTOR">Подрядчик</option></select></label>
        {depthIndex(values.calculationDepth) >= 2 && <label className="block">Техподдержка при RaaS<select id="economics-staffing-raas" className="block w-full border rounded p-2" value={values.technicianRaasMode} onChange={set('technicianRaasMode')}><option value="">Выберите покрытие</option><option value="TRANSFER">Перевод квалифицированного сотрудника</option><option value="HIRE">Отдельный найм</option><option value="EXISTING">Существующая функция</option><option value="CONTRACTOR">Подрядчик</option><option value="VENDOR">Поставщик, включено в RaaS</option></select></label>}
        {(values.technicianPurchaseMode === 'TRANSFER' || values.technicianRaasMode === 'TRANSFER') && <label className="flex gap-2"><input type="checkbox" checked={values.qualifiedTechTransfer} onChange={set('qualifiedTechTransfer')} />Подтверждаю квалификацию переводимого сотрудника для техподдержки</label>}
        <p>Зарплата или стоимость услуги запрашивается ниже только для непокрытой функции. Неизвестная стоимость даёт частичный результат; выбор и источник сохраняются в новом расчёте.</p>
      </div>}
      {group === 'Труд' && roleRefs.length > 1 && <div className="block mt-3 rounded border border-amber-400 bg-amber-50 p-3 text-sm"><label>Основная роль операции
        <select id="economics-primary_role_id" value={values.primaryRoleId} onChange={(event) => setValues((current) => changeManualProductivityRole(current, event.target.value))} className="w-full border rounded p-2"><option value="">Не выбрано — труд и деньги останутся частичными</option>{roleRefs.map((id, index) => <option key={id} value={id}>{roleName(capacityRequest?.role_pool?.roles?.find((role) => role.role_id === id)?.role_code) || `Роль ${index + 1}`}</option>)}</select></label>
        <small>Ниже задайте долю работы и ручную выработку каждой дополнительной роли. Нулевая доля — проектное допущение, которое нужно подтвердить: эта роль остаётся в штате и экономия по ней равна нулю.</small>
        {roleRefs.filter((id) => id !== selectedRoleId).map((id) => {
          const role = capacityRequest?.role_pool?.roles?.find((item) => item.role_id === id);
          const profile = values.roleWorkProfiles?.[id] || {};
          return <div key={id} className="mt-3 rounded border border-amber-300 bg-white p-3 space-y-2">
            <strong>{roleName(role?.role_code) || id}</strong>
            {(role?.process_ids?.length > 1 || Object.hasOwn(profile, 'allocationFraction')) && <label className="block">Доля штата этой роли в текущем процессе (0–1)<input type="number" min="0" max="1" step="any" value={profile.allocationFraction ?? ''} onChange={setRoleWork(id, 'allocationFraction')} className="block w-full border rounded p-2" /><small>Укажите часть общего штата роли; сумма долей по процессам объекта не должна превышать 1.</small></label>}
            <label className="block">Доля работы, заменяемой роботом (0–1)<input type="number" min="0" max="1" step="any" value={profile.fraction ?? '0'} onChange={setRoleWork(id, 'fraction')} className="block w-full border rounded p-2" /></label>
            <label className="block">Ручная выработка этой роли, ед./смену<input type="number" min="0" step="any" value={profile.manual ?? ''} onChange={setRoleWork(id, 'manual')} className="block w-full border rounded p-2" /></label>
            <small>Нужна, если доля больше нуля; берите замер или явно помечайте оценку.</small>
            <label className="block">Какая работа остаётся<input value={profile.residual ?? (Number(profile.fraction ?? '0') === 0 ? ZERO_ROLE_RESIDUAL : '')} onChange={setRoleWork(id, 'residual')} className="block w-full border rounded p-2" /></label>
            <label className="block">Основание доли и выработки<input value={profile.basis ?? (Number(profile.fraction ?? '0') === 0 ? ZERO_ROLE_BASIS : '')} onChange={setRoleWork(id, 'basis')} className="block w-full border rounded p-2" /></label>
            <label className="block">Тип данных<select value={profile.source || 'ASSUMPTION'} onChange={setRoleWork(id, 'source')} className="block w-full border rounded p-2"><option value="ASSUMPTION">Проектное допущение</option><option value="USER">Замер или данные объекта</option></select></label>
            <label className="flex gap-2"><input type="checkbox" checked={profile.confirmed === true} onChange={setRoleWork(id, 'confirmed')} />Подтверждаю данные и основание по этой роли для нового расчёта</label>
          </div>;
        })}</div>}
      {group === 'Труд' && roleRefs.length > 0 && <div className="mt-3 rounded border border-teal-300 bg-teal-50 p-3 text-sm space-y-2" aria-label="Исходные данные и подтверждение ролей">
        <strong>Штат и месячные суммы из сохранённого шага «Работа»</strong>
        <ul>{roleRefs.map((id) => {
          const role = capacityRequest?.role_pool?.roles?.find((item) => item.role_id === id);
          return <li key={id}>{roleName(role?.role_code) || id}: {formatDecimal(role?.headcount?.normalized_value) ?? 'неизвестно'} чел.,
            {formatDecimal(role?.monthly_gross_salary?.normalized_value) ?? 'сумма неизвестна'} ₽/чел./мес.</li>;
        })}</ul>
        <small>Если штат или сумма неверны, измените их на шаге «Работа» и сохраните новый технический расчёт. Доля и выработка ниже относятся только к выбранному процессу.</small>
        {selectedRoleId && <div className="mt-2 rounded border bg-white p-3 space-y-2">
          <strong>{roleName(selectedRole?.role_code) || selectedRoleId}: источник доли и выработки</strong>
          {(selectedRole?.process_ids?.length > 1 || Object.hasOwn(values.roleWorkProfiles?.[selectedRoleId] || {}, 'allocationFraction')) && <label className="block">Доля штата этой роли в текущем процессе (0–1)<input type="number" min="0" max="1" step="any" value={values.roleWorkProfiles?.[selectedRoleId]?.allocationFraction ?? ''} onChange={setRoleWork(selectedRoleId, 'allocationFraction')} className="block w-full border rounded p-2" /><small>Укажите часть общего штата роли; сумма долей по процессам объекта не должна превышать 1.</small></label>}
          <label className="block">Тип данных<select value={values.roleWorkProfiles?.[selectedRoleId]?.source || 'ASSUMPTION'} onChange={setRoleWork(selectedRoleId, 'source')} className="block w-full border rounded p-2"><option value="ASSUMPTION">Проектное допущение</option><option value="USER">Замер или данные объекта</option></select></label>
          <small>Если хотя бы доля или выработка оценочная, оставьте «Проектное допущение». У выработки ниже есть отдельный источник числового значения.</small>
          <label className="block">Основание: документ, период замера или причина допущения<input value={values.roleWorkProfiles?.[selectedRoleId]?.basis ?? (values.roleWorkProfiles?.[selectedRoleId]?.source === 'USER' ? '' : PRIMARY_ROLE_BASIS)} onChange={setRoleWork(selectedRoleId, 'basis')} className="block w-full border rounded p-2" /></label>
          <label className="flex gap-2"><input type="checkbox" checked={values.roleWorkProfiles?.[selectedRoleId]?.confirmed === true} onChange={setRoleWork(selectedRoleId, 'confirmed')} />Подтверждаю распределение штата, долю работы, выработку и основание этой роли для нового расчёта</label>
        </div>}
      </div>}
      {group === 'Труд' && <div className="mt-3 rounded border border-teal-300 p-3 text-sm" aria-label="Оценка ручной выработки">
        <strong>Выработка одного сотрудника {roleLabel} в процессе «{processLabel}»</strong>
        <p>Объём: {presentationValue('', process?.demand?.normalized_value, process?.demand?.unit)}; смен: {formatDecimal(process?.schedule?.shifts_per_day?.normalized_value) ?? 'неизвестно'}; показатель определяет потребность в персонале и экономию оплаты труда только выбранной роли.</p>
        {manualEstimate?.status === 'ESTIMATE' && <div className="mt-2"><p><strong>≈ {estimateShown} {process?.scope === 'CLEANING_AREA' ? 'м² на сотрудника за смену' : process?.scope === 'PALLET_TRANSPORT' ? 'паллеты на сотрудника за смену' : 'единиц на сотрудника за смену'}</strong>. Предварительная оценка, не замер.</p>
          <p>{process?.scope === 'CLEANING_AREA' ? 'Механизированная база уборки × полезное время смены.' : 'Полезное время смены делится на время рейса туда и обратно с приёмом и передачей груза.'}</p>
          <dl className="productivity-inputs">
            <div><dt>Длительность смены</dt><dd>{formatDecimal(process?.schedule?.shift_hours?.normalized_value) ?? 'неизвестно'} ч</dd></div>
            <div><dt>Полезное время</dt><dd>{formatPercent(manualEstimate.inputs.useful_time_share)}</dd></div>
            {process?.scope === 'CLEANING_AREA' ? <div><dt>Механизированная выработка</dt><dd>{formatDecimal(manualEstimate.inputs.mechanized_rate_m2_h) ?? 'неизвестно'} м²/ч</dd></div> : <>
              <div><dt>Маршрут в одну сторону</dt><dd>{formatDecimal(process?.route_distance?.normalized_value) ?? 'неизвестно'} м; обратно — тот же маршрут</dd></div>
              <div><dt>Скорость человека</dt><dd>{formatDecimal(manualEstimate.inputs.manual_speed_m_s) ?? 'неизвестно'} м/с</dd></div>
              <div><dt>Приём и передача</dt><dd>{formatDecimal(manualEstimate.inputs.manual_exchange_s) ?? 'неизвестно'} с</dd></div>
              <div><dt>Груз за рейс</dt><dd>{formatDecimal(manualEstimate.inputs.units_per_trip) ?? 'неизвестно'} ед.</dd></div>
            </>}
          </dl><small>Источник: допущения типового процесса. Полная методика сохранена в архиве.</small></div>}
        {manualEstimate?.status === 'ESTIMATE' && selectedRoleId && <button type="button" className="secondary-action mt-2" onClick={() => setValues((current) => {
          const next = applyManualProductivityEstimate(current, manualEstimate);
          return { ...next, roleWorkProfiles: { ...next.roleWorkProfiles,
            [selectedRoleId]: { ...next.roleWorkProfiles?.[selectedRoleId], source: 'ASSUMPTION', confirmed: false } } };
        })}>Взять оценку как допущение для выбранной роли</button>}
        {manualEstimate?.status === 'UNSUPPORTED' && <p className="mt-2 text-amber-800">Для этого процесса нет утверждённой оценки ручной выработки. Введите измеренную норму; расчёт без неё останется частичным.</p>}
        {process?.scope === 'CLEANING_AREA' && <p className="mt-2">Для уборки укажите ручную выработку за смену; оценка реестра доступна как предварительное допущение.</p>}
      </div>}
      {group === 'Визуализация' && <div className="mt-2 rounded border p-3 text-sm">
        <p>Модельное начало: понедельник, {String(Math.floor(Number(values.startSeconds) / 3600)).padStart(2, '0')}:{String(Math.floor(Number(values.startSeconds) % 3600 / 60)).padStart(2, '0')} местного времени. Часовой пояс сохраняется в новом сценарии.</p>
        <label className="mt-2 block">Часовой пояс<select id="economics-timezone" value={values.timezone} onChange={set('timezone')} className="block w-full border rounded p-2"><option value="">Выберите часовой пояс</option>{timezoneChoices(values.timezone).map((zone) => <option key={zone} value={zone}>{zone.replaceAll('_', ' ')}</option>)}</select></label>
        <details className="mt-2"><summary>Детальная настройка модельного времени</summary><label className="mt-2 block">Начало смены · местное время<input id="economics-start_seconds_from_midnight" type="time" value={`${String(Math.floor(Number(values.startSeconds) / 3600)).padStart(2, '0')}:${String(Math.floor(Number(values.startSeconds) % 3600 / 60)).padStart(2, '0')}`} onChange={(event) => { const [h, m] = event.target.value.split(':').map(Number); setValues((current) => ({ ...current, startSeconds: String(h * 3600 + m * 60) })); }} className="block border rounded p-2" /></label><p>График смен из процесса сохраняется. Здесь задаётся только местное начало.</p></details>
      </div>}
      {group !== 'Визуализация' && <details open={group !== 'Покупка'} className="mt-3 rounded border p-3"><summary className="cursor-pointer font-semibold">{group === 'Покупка' ? 'Уточнить затраты и условия покупки' : 'Данные для расчёта'}</summary><div className="mt-2 grid gap-3 md:grid-cols-3">{FIELDS.filter((field) => field[0] === group && visibleField(field)).map(([, key, server, label, unit, why, source]) => {
        const fieldIssues = issues.filter((item) => item.field === server);
        const staffingField = ['control_transfer_monthly_supplement_gross', 'technician_transfer_monthly_supplement_gross', 'technician_contractor_annual_gross'].includes(server);
        const displayLabel = key === 'manualUnitsPerShift' ? `Выработка одного сотрудника ${roleLabel} в процессе «${processLabel}»`
          : key === 'averagePowerW' && values.energyPowerBasis === 'MAX_UPPER_BOUND' ? 'Максимальная паспортная мощность робота' : label;
        return <div key={key} className="block rounded border border-slate-500/40 p-3 text-sm">
          <label htmlFor={`economics-${server}`} className="block"><strong>{displayLabel}</strong> · {unit}</label>

          <input id={`economics-${server}`} type="text" inputMode="decimal" aria-label={displayLabel} value={values[key]} onChange={(event) => setValues((current) => {
            const next = editEconomicsField(current, key, server, event.target.value, { enableTemplate: demoEligible });
            return key === 'manualUnitsPerShift' ? unconfirmPrimary(next, current) : next;
          })} className="w-full border rounded p-2 mt-2" placeholder="Неизвестно — оставьте пустым" aria-invalid={fieldIssues.some((item) => !['MISSING_INPUT', 'RANGE_ONLY'].includes(item.code))} />
          <details className="mt-2"><summary className="text-xs cursor-pointer">Источник и допущения</summary><small className="block mt-1">{why} Возможный источник: {source}. {['Покупка', 'RaaS'].includes(group) ? 'Коммерческое условие требует отдельной проверки.' : ''}</small>
          {!staffingField && <select value={values.sources[server] || 'USER'} onChange={(event) => setValues((current) => {
            const next = event.target.value === 'USER' ? chooseUserField(current, key, server)
              : proposeDemoField(current, key, server, { enableTemplate: demoEligible });
            return key === 'manualUnitsPerShift' ? unconfirmPrimary(next, current) : next;
          })} aria-label={`Тип источника: ${label}`} className="w-full border rounded p-2 mt-1">
            <option value="USER">Данные пользователя</option><option value="ASSUMPTION">Допущение для сценария</option>
          </select>}
          {values.sources[server] === 'ASSUMPTION' && <div className="mt-2 rounded bg-amber-50 p-2 text-xs">
            {demoEligible && WAREHOUSE_ECONOMICS_DEMO.fields[server] ? <p>Допущение типового примера от {WAREHOUSE_ECONOMICS_DEMO.published_on}: {presentationValue(server, WAREHOUSE_ECONOMICS_DEMO.fields[server].value, WAREHOUSE_ECONOMICS_DEMO.fields[server].unit)}. {fieldPresentation(server).action}</p>
              : <p>Для этого поля нет шаблона. Введите число вручную и подтвердите его как ваше сценарное допущение.</p>}
            {values[key] !== '' && values.assumptions[server] && <label className="mt-1 flex gap-2"><input type="checkbox" checked={values.assumptions[server].confirmed === true} onChange={(event) => setValues((current) => confirmEconomicsAssumption(current, server, event.target.checked))} />Подтверждаю число {values[key]} для этого сценария</label>}
            {values[key] !== '' && !values.assumptions[server] && <p>Нужно ввести и подтвердить число.</p>}
          </div>}
          </details>
          {fieldIssues.map((item, index) => <small key={index} className={`block mt-1 ${['MISSING_INPUT', 'RANGE_ONLY'].includes(item.code) ? 'text-amber-900' : 'text-red-700'}`} role="status">{humanizePresentation(item.message)} {humanizePresentation(item.next_step)}</small>)}
        </div>;
      })}</div></details>}
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
      {CHECKS.filter(([group, key]) => key !== 'grossConfirm' && (group === 'Покупка' && depthIndex(values.calculationDepth) >= 1 || group === 'RaaS' && depthIndex(values.calculationDepth) >= 2)).map(([, key, server, label]) => <label key={key} className="mt-3 flex gap-2 rounded border p-2"><input id={`economics-condition-${key}`} type="checkbox" checked={values[key]} onChange={set(key)} /><span>{label}<small className="block">{ECONOMICS_CONDITIONS.find((item) => item.key === key)?.consequence}</small>{issues.some((item) => item.field === server) && <small className="block text-red-700">Нужно для этой ветки.</small>}</span></label>)}
    </section>
    <p className="text-sm">Пригодность на объекте и закупочная готовность проверяются отдельно. Этот расчёт не подтверждает поставщика и не даёт рекомендации к закупке.</p>
    {error && <p className="text-red-700" role="alert">{error}</p>}
    <div className="flex flex-wrap gap-3"><button type="button" disabled={busy} onClick={submit} className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-50">{busy ? 'Сохраняем…' : 'Рассчитать и сохранить выбранный уровень'}</button>
      {values.calculationDepth === 'FULL' && !readiness.fullReady && <button type="button" className="secondary-action" onClick={goToMissing}>Показать недостающие входы</button>}</div>
    <p className="text-sm">Каждый уровень сохраняется и скачивается. Глубина описывает состав выбранных входов; фактически рассчитанные ветки и неизвестные данные отдельно указаны в результате.</p>
  </form>;
}
