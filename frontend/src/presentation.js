import glossary from '../../contracts/presentation-v2.json' with { type: 'json' };
import current from '../../contracts/user-presentation-v3.json' with { type: 'json' };
import { formatDecimal, formatPercent } from './displayNumber.js';

export const PRESENTATION_VERSION = glossary.version;
export const subsystemLabel = (code) => glossary.subsystems[code] || 'раздел расчёта';
export const statusLabel = (code) => current.statuses[code] || glossary.statuses[code] || 'требуется уточнение';
export const sectionLabel = (code) => glossary.sections[code] || 'Раздел данных';
export const unitLabel = (unit) => current.units[unit] || (/^[а-яА-ЯёЁ₽%²/ .0-9]+$/.test(unit || '') ? unit : '');
export const reasonLabel = (code) => current.reasons[code] || 'Требуется проверить исходные условия и пригодность';
export const sourceLabel = (item = {}) => /автор|типов|test|fixture|demo/i.test(`${item.source || ''} ${item.rationale || ''}`)
  ? 'Допущение типового примера' : item.source === 'USER' ? 'Данные пользователя' : item.source === 'ASSUMPTION'
    ? 'Сценарное допущение' : /catalog|организатор/i.test(item.source || '') ? 'Сохранённый каталог' : 'Сохранённый источник';

export function presentationValue(field, value, unit = '') {
  if (value == null || value === '') return 'Не указано';
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
  if (field === 'start_seconds_from_midnight') {
    const seconds = Number(value);
    return Number.isFinite(seconds) && seconds >= 0 && seconds < 86400
      ? `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')} · местное время` : 'Не указано';
  }
  if (['discount_rate', 'fraction', 'useful_time_share'].includes(field)) return formatPercent(value);
  if (current.statuses[value]) return current.statuses[value];
  const resolvedUnit = current.fields[field]?.unit || unit || (/_gross$/.test(field) ? 'RUB' : '');
  const number = formatDecimal(value, 2, resolvedUnit.startsWith('RUB') ? 2 : 0);
  return number == null ? humanizePresentation(String(value)) : `${number} ${unitLabel(resolvedUnit)}`.trim();
}

export function humanizePresentation(value) {
  if (typeof value !== 'string') return '';
  let text = value;
  for (const [key, label] of Object.entries(glossary.terms || {})) text = text.replaceAll(key, label);
  text = text.replace(/\bC\d{2}\b/g, (code) => subsystemLabel(code));
  for (const [code, label] of Object.entries(glossary.statuses)) {
    text = text.replace(new RegExp(`\\b${code}\\b`, 'g'), label);
  }
  for (const [key, entry] of Object.entries(glossary.fields).sort((a, b) => b[0].length - a[0].length)) {
    text = text.replaceAll(key, entry.label);
  }
  for (const [code, label] of Object.entries(current.reasons)) text = text.replaceAll(code, label);
  for (const [code, label] of Object.entries(current.statuses)) text = text.replace(new RegExp(`\\b${code}\\b`, 'g'), label);
  return text.replace(/\b[FRK]\d{2}\b/g, 'расчётный показатель')
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, 'идентификатор в архиве')
    .replace(/(?:sha256:)?\b[0-9a-f]{64}\b/gi, 'контрольная сумма в архиве')
    .replace(/\b(?:backend|frontend|contracts|tests?|registry|conversion)[/.][^\s,;]+/gi, 'источник в архиве')
    .replace(/\b[A-Z][A-Z0-9_]+_[A-Z0-9_]+\b/g, 'требует уточнения')
    .replace(/финансовые? runs?/gi, 'сохранённые финансовые расчёты');
}

export function fieldPresentation(key) {
  if (typeof key !== 'string') return { label: 'дополнительное условие', action: 'Уточните входные данные.' };
  if (key.startsWith('role_pool.')) return {
    label: 'зарплата роли процесса', action: 'Уточните месячную зарплату этой роли во вводе процесса и создайте новый расчёт парка.',
  };
  return current.fields[key] || glossary.fields[key] || { label: 'дополнительное условие', action: 'Сверьте условие и источник в архиве расчёта.' };
}

export function savedCalculationLabel(date) {
  if (!date) return 'Сохранённый расчёт';
  const value = new Date(date);
  return Number.isNaN(value.getTime()) ? 'Сохранённый расчёт' :
    `Сохранённый расчёт от ${new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(value)}`;
}
