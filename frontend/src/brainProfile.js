import { createDraft, updateProcess, updateRole, setRoleActive, updateZone, serializeDraft } from './processRoleIntakeV2.js';

export const BRAIN_FIELDS = [
  ['object_type', 'Тип объекта', '', 'choice', [['retail', 'Склад'], ['airport', 'Аэропорт'], ['clinic', 'Клиника'], ['other', 'Другое']]],
  ['process_type', 'Операция', '', 'choice', [['transport', 'Перевозка паллет'], ['cleaning', 'Уборка'], ['unsupported', 'Другая операция']]],
  ['operations_per_day', 'Объём в сутки', 'паллет/сутки'],
  ['shifts_count', 'Смен в сутки', 'смен'],
  ['shift_hours', 'Часов в смене', 'ч'],
  ['operating_days', 'Рабочих дней в году', 'дней'],
  ['avg_distance_m', 'Плечо в одну сторону', 'м'],
  ['units_per_trip', 'Груз за рейс', 'паллет/рейс'],
  ['exchange_seconds', 'Погрузка и выгрузка за рейс', 'сек'],
  ['cleaning_frequency_per_day', 'Уборок этой площади в сутки', 'раз/сутки'],
  ['zone_label', 'Зона или маршрут', ''],
  ['zone_constraints', 'Ограничения зоны', ''],
  ['staff_headcount', 'Сотрудников сейчас', 'чел.'],
  ['monthly_gross_salary', 'Зарплата gross на человека', '₽/мес.'],
  ['manual_units_per_shift', 'Ручная выработка за смену', 'паллет/смену'],
];

const confirmed = (profile, key) => profile?.fields?.[key]?.confirmed_by_user ? profile.fields[key].value : '';

export function makeBrainDraft(profile, processCode = null) {
  if (confirmed(profile, 'object_type') !== 'retail') throw new Error('Для этого объекта пока нет поддержанного расчётного профиля.');
  const process = confirmed(profile, 'process_type');
  const code = processCode || (process === 'cleaning' ? 'warehouse_cleaning' : 'warehouse_receiving_shipping');
  if (!['warehouse_receiving_shipping', 'warehouse_cleaning'].includes(code)) throw new Error('У этой операции пока нет формулы C11.');
  if ((process === 'transport' && code !== 'warehouse_receiving_shipping') ||
      (process === 'cleaning' && code !== 'warehouse_cleaning')) {
    throw new Error('Для второго процесса создайте дочернюю версию профиля: укажите его объём и режим отдельно.');
  }
  let draft = createDraft('retail');
  draft = updateZone(draft, draft.zones[0].zoneId, {
    label: confirmed(profile, 'zone_label') || 'Основная зона',
    constraints: confirmed(profile, 'zone_constraints'),
  });
  draft = updateProcess(draft, code, {
    active: true, demand: confirmed(profile, 'operations_per_day'), shifts: confirmed(profile, 'shifts_count'),
    hours: confirmed(profile, 'shift_hours'), days: confirmed(profile, 'operating_days'),
    distance: code === 'warehouse_receiving_shipping' ? confirmed(profile, 'avg_distance_m') : '',
    batch: code === 'warehouse_receiving_shipping' ? confirmed(profile, 'units_per_trip') : '',
    fieldSources: Object.fromEntries([
      ['demand', 'operations_per_day'], ['shifts', 'shifts_count'], ['hours', 'shift_hours'],
      ['days', 'operating_days'], ['distance', 'avg_distance_m'], ['batch', 'units_per_trip'],
    ].map(([key, field]) => [key, profile.fields[field]?.provenance === 'expert_assumption' ? 'ASSUMPTION' : 'USER'])),
    fieldConfirmations: { batch: Boolean(confirmed(profile, 'units_per_trip')) },
  });
  if (confirmed(profile, 'staff_headcount')) {
    const roleCode = code === 'warehouse_cleaning' ? 'cleaner' : 'forklift_driver';
    draft = setRoleActive(draft, code, roleCode, true);
    draft = updateRole(draft, `${draft.objectId}.${roleCode}`, {
      headcount: confirmed(profile, 'staff_headcount'), salary: confirmed(profile, 'monthly_gross_salary'),
      salarySource: profile.fields.monthly_gross_salary?.provenance === 'expert_assumption' ? 'ASSUMPTION' : 'USER',
      salaryConfirmed: Boolean(confirmed(profile, 'monthly_gross_salary')),
    });
  }
  return { draft, request: serializeDraft(draft) };
}

export function profileInputDiff(before, after) {
  const keys = new Set([...Object.keys(before?.fields || {}), ...Object.keys(after?.fields || {})]);
  return [...keys].filter((key) => before?.fields?.[key]?.value !== after?.fields?.[key]?.value)
    .map((key) => ({ key, from: before?.fields?.[key]?.value ?? '—', to: after?.fields?.[key]?.value ?? '—' }));
}

export function capacityKpiDiff(before, after) {
  const oldValue = before?.result_snapshot?.capacity?.value || before?.capacity?.value;
  const newValue = after?.result_snapshot?.capacity?.value || after?.capacity?.value;
  if (!oldValue || !newValue) return [];
  return [
    ['recommended_fleet', 'Рекомендованный парк'],
    ['selected_fleet', 'Выбранный парк'],
    ['effective_capacity', 'Эффективная производительность'],
    ['coverage', 'Покрытие'],
    ['raw_load_ratio', 'Фактическая загрузка'],
  ].map(([key, label]) => {
    const display = (value) => value && typeof value === 'object' ? `${value.value} ${value.unit}` : String(value ?? '—');
    return { key, label, from: display(oldValue[key]), to: display(newValue[key]) };
  }).filter((item) => item.from !== item.to);
}
