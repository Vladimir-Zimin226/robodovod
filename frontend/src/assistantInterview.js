import { createDraft, setRoleActive, updateProcess, updateRole, updateZone } from './processRoleIntakeV2.js';

export const PROFILE_VERSION = 'assistant-interview-profile-v1';
export const SESSION_TTL_MS = 8 * 60 * 60 * 1000;
export const STARTER_QUESTIONS = [
  'Что умеет сервис?', 'Какие данные нужны?', 'Можно считать без цены?',
  'Чем допущение отличается от факта?', 'Почему нет денежного эффекта?', 'Где посмотреть 2D?',
  'Что значат проверка пригодности и закупка?', 'Как сравнить роботов?',
];
export const INTERVIEW_FIELDS = [
  { key: 'object_type', label: 'Объект', step: 'Процесс', kind: 'choice', options: [['retail', 'Склад']] },
  { key: 'process_type', label: 'Операция', step: 'Процесс', kind: 'choice', options: [['transport', 'Перемещение паллет'], ['cleaning', 'Уборка склада']] },
  { key: 'cargo_type', label: 'Груз или объект операции', step: 'Груз и операция', kind: 'text' },
  { key: 'operations_per_day', label: 'Объём в сутки, паллет или м²', step: 'Объём и пики', kind: 'number' },
  { key: 'peak_multiplier', label: 'Пиковый множитель, если известен', step: 'Объём и пики', kind: 'number' },
  { key: 'shifts_count', label: 'Смен в сутки', step: 'Режим', kind: 'number' },
  { key: 'shift_hours', label: 'Часов в смене', step: 'Режим', kind: 'number' },
  { key: 'operating_days', label: 'Рабочих дней в году', step: 'Режим', kind: 'number' },
  { key: 'avg_distance_m', label: 'Плечо маршрута, м', step: 'Маршрут и зоны', kind: 'number' },
  { key: 'units_per_trip', label: 'Сколько паллет (или иных единиц груза) робот перевозит за один рейс?', step: 'Маршрут и зоны', kind: 'number' },
  { key: 'zone_label', label: 'Название зоны', step: 'Маршрут и зоны', kind: 'text' },
  { key: 'zone_constraints', label: 'Ограничения зоны', step: 'Маршрут и зоны', kind: 'text' },
  { key: 'staff_headcount', label: 'Сотрудников сейчас', step: 'Персонал и экономика', kind: 'number' },
  { key: 'monthly_gross_salary', label: 'Зарплата gross, ₽/чел./мес.', step: 'Персонал и экономика', kind: 'number' },
];
export const INTERVIEW_STEPS = [...new Set(INTERVIEW_FIELDS.map((field) => field.step))];
const NUMERIC = new Set(INTERVIEW_FIELDS.filter((field) => field.kind === 'number').map((field) => field.key));
const MAPPED = {
  pallets_per_day: 'operations_per_day', avg_distance_m: 'avg_distance_m',
  shifts_count: 'shifts_count', staff_headcount: 'staff_headcount',
};

export const emptyProfile = () => ({ schema_version: PROFILE_VERSION, fields: {} });

export function editProfile(profile, key, value) {
  if (!INTERVIEW_FIELDS.some((field) => field.key === key)) throw new Error('UNKNOWN_INTERVIEW_FIELD');
  const fields = { ...profile.fields };
  if (value === '') delete fields[key];
  else fields[key] = { value: String(value), source: 'USER_ENTRY', evidence: '', confirmed: false };
  return { ...profile, fields };
}

export function confirmField(profile, key, confirmed) {
  if (!profile.fields[key]) return profile;
  return { ...profile, fields: { ...profile.fields,
    [key]: { ...profile.fields[key], confirmed: Boolean(confirmed) } } };
}

export function mergeAssistantDraft(profile, draft) {
  const fields = { ...profile.fields };
  const conflicts = [];
  const mapped = { ...draft?.fields };
  if (mapped.process_type === 'transport' && mapped.cargo_type === 'pallets') mapped.object_type = 'retail';
  if (mapped.object_type === 'other') delete mapped.object_type;
  for (const [from, raw] of Object.entries(mapped)) {
    const key = MAPPED[from] || from;
    if (!INTERVIEW_FIELDS.some((field) => field.key === key) || raw == null) continue;
    const value = String(raw);
    if (fields[key]?.value && fields[key].value !== value) { conflicts.push(key); continue; }
    if (!fields[key]) fields[key] = { value, source: 'USER_STATEMENT', evidence: draft.summary || '', confirmed: false };
  }
  return { profile: { ...profile, fields }, conflicts };
}

export function profileReadiness(profile) {
  const fields = profile.fields || {};
  const known = (key) => Boolean(fields[key]?.value && fields[key]?.confirmed);
  const process = fields.process_type?.value;
  const capacity = ['object_type', 'process_type', 'operations_per_day', 'shifts_count', 'shift_hours', 'operating_days',
    ...(process === 'transport' ? ['avg_distance_m', 'units_per_trip'] : [])];
  const labour = [...capacity, 'staff_headcount', 'monthly_gross_salary'];
  const invalid = [];
  for (const key of NUMERIC) {
    const value = fields[key]?.value;
    if (value == null) continue;
    if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)
      || (key !== 'monthly_gross_salary' && Number(value) <= 0)) invalid.push(key);
  }
  if (Number(fields.shifts_count?.value) * Number(fields.shift_hours?.value) > 24) invalid.push('shifts_count');
  if (fields.units_per_trip?.value && !/^[1-9]\d*$/.test(fields.units_per_trip.value)) invalid.push('units_per_trip');
  if ((fields.zone_label?.value != null && !fields.zone_label.value.trim())
    || fields.zone_label?.value?.length > 128 || fields.zone_constraints?.value?.length > 1000) invalid.push('zone_label');
  if (Number(fields.shifts_count?.value) > 4 || Number(fields.shift_hours?.value) > 24
    || Number(fields.operating_days?.value) > 366) invalid.push('shifts_count');
  if (fields.monthly_gross_salary?.value && !fields.staff_headcount?.value) invalid.push('staff_headcount');
  return {
    capacity: capacity.filter((key) => !known(key)),
    labour: labour.filter((key) => !known(key)),
    economics: ['Ручная выработка, условия покупки и аренды, ставка и горизонт заполняются после расчёта парка'],
    visualization: ['Время начала и часовой пояс заполняются после расчёта парка'],
    unconfirmed: Object.keys(fields).filter((key) => !fields[key].confirmed),
    invalid: [...new Set(invalid)],
  };
}

export function canImportProfile(profile) {
  const ready = profileReadiness(profile);
  const values = profile.fields;
  if (ready.capacity.length || ready.unconfirmed.length || ready.invalid.length || values.object_type?.value !== 'retail'
    || !['transport', 'cleaning'].includes(values.process_type?.value)) return false;
  return true;
}

export function toV2Draft(profile) {
  if (!canImportProfile(profile)) throw new Error('Подтвердите обязательные поля и исправьте числовые значения.');
  const get = (key) => profile.fields[key]?.confirmed ? profile.fields[key].value : '';
  let draft = createDraft('retail');
  const processType = get('process_type');
  const code = processType === 'cleaning' ? 'warehouse_cleaning' : 'warehouse_receiving_shipping';
  draft = updateZone(draft, draft.zones[0].zoneId, {
    label: get('zone_label') || 'Основная зона', constraints: get('zone_constraints'),
  });
  draft = updateProcess(draft, code, {
    active: true, demand: get('operations_per_day'), shifts: get('shifts_count'),
    hours: get('shift_hours'), days: get('operating_days'),
    distance: processType === 'transport' ? get('avg_distance_m') : '',
    batch: processType === 'transport' ? get('units_per_trip') : '',
  });
  if (get('staff_headcount')) {
    const roleCode = processType === 'cleaning' ? 'cleaner' : 'forklift_driver';
    draft = setRoleActive(draft, code, roleCode, true);
    draft = updateRole(draft, `${draft.objectId}.${roleCode}`, {
      headcount: get('staff_headcount'), salary: get('monthly_gross_salary'),
      salarySource: 'USER', salaryConfirmed: true,
    });
  }
  return draft;
}

export function readGuestProfile(storage, now = Date.now()) {
  try {
    const saved = JSON.parse(storage?.getItem('robodovod.assistant.guest.v1') || 'null');
    if (saved?.expires_at > now && saved.profile?.schema_version === PROFILE_VERSION) return saved.profile;
  } catch { /* private mode or expired data */ }
  return emptyProfile();
}

export function writeGuestProfile(storage, profile, now = Date.now()) {
  try { storage?.setItem('robodovod.assistant.guest.v1', JSON.stringify({ profile, expires_at: now + SESSION_TTL_MS })); }
  catch { /* session storage can be unavailable */ }
}
