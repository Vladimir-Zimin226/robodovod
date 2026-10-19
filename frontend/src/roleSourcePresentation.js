const WORKBOOK_CELL = /(?:Склад|Аэропорт|Медучреждение|Клиника)!C\d+(?:\+C\d+)*/gi;
const INTERNAL_ROW = /\bRW-[A-Z0-9_-]+:\s*/gi;

export function readableBasis(value) {
  if (!value) return '';
  const cleaned = String(value)
    .replace(INTERNAL_ROW, '')
    .replace(WORKBOOK_CELL, '')
    .replace(/\bC\d+\b/gi, '')
    .replace(/\bASSUMPTION(?:_V\d+)?\b/gi, 'допущение авторов')
    .replace(/\b(?:RW-[A-Z0-9_-]+|[a-z]+(?:_[a-z]+)+)\b/g, '')
    .replace(/^\s*[=,:]\s*/, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
  return cleaned || 'Типовое значение принято авторами сценария; уточните его по данным объекта.';
}

export function sourceLabel(value) {
  const source = String(value || '').toUpperCase();
  if (source.startsWith('USER') || source === 'MEASUREMENT') return 'Ваши данные';
  if (source.startsWith('CATALOG')) return 'Данные каталога; проверьте применимость';
  if (source.startsWith('FORMULA') || source.startsWith('CALCULATED')) return 'Расчёт по формуле';
  return 'Допущение авторов';
}

export function basisSourceLabel(value) {
  return /(?:\bRW-[A-Z0-9_-]+:|(?:Склад|Аэропорт|Медучреждение|Клиника)!C\d+)/i.test(String(value || ''))
    ? 'Допущение авторов' : 'Ваши данные';
}

export function calculationLabel(status) {
  if (status === 'REFERENCE_ONLY') return 'Сценарная оценка выработки; паспортная скорость модели не подтверждена.';
  if (status === 'CALCULABLE') return 'Расчёт по введённым объёмам и сценарной выработке.';
  if (status === 'SAFETY_BLOCKED') return 'Условный расчёт: требуется подтвердить допуск.';
  return 'Расчёт по введённым данным и допущениям.';
}

export function modelLabel(status) {
  if (status === 'NO_ROBOT') return 'Робот для этой работы не выбран';
  if (status === 'NO_CATALOG_MATCH_SCENARIO_TYPE') return 'Подходящая модель в каталоге не найдена; использован сценарный тип';
  if (status === 'SCENARIO_TYPE_SELECTED') return 'Использован сценарный тип без каталожной модели';
  return 'Каталожная модель требует проверки на объекте';
}

export function missingInputLabel(value) {
  const field = String(value).split('.').at(-1);
  if (field === 'scenario_purchase_price_rub') return 'цена покупки робота';
  if (field === 'scenario_raas_monthly_rub') return 'месячный тариф аренды';
  return 'условия расчёта';
}
