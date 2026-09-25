import glossary from '../../contracts/presentation-v2.json' with { type: 'json' };

export const PRESENTATION_VERSION = glossary.version;
export const subsystemLabel = (code) => glossary.subsystems[code] || 'раздел расчёта';
export const statusLabel = (code) => glossary.statuses[code] || 'требуется уточнение';
export const sectionLabel = (code) => glossary.sections[code] || 'Раздел данных';

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
  return text.replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, 'идентификатор в технических подробностях');
}

export function fieldPresentation(key) {
  if (typeof key !== 'string') return { label: 'дополнительное условие', action: 'Уточните входные данные.' };
  if (key.startsWith('role_pool.')) return {
    label: 'зарплата роли процесса', action: 'Уточните месячную зарплату этой роли во вводе процесса и создайте новый расчёт парка.',
  };
  return glossary.fields[key] || { label: 'дополнительное условие', action: 'Откройте технические подробности, чтобы сверить имя поля и источник.' };
}

export function savedCalculationLabel(date) {
  if (!date) return 'Сохранённый расчёт';
  const value = new Date(date);
  return Number.isNaN(value.getTime()) ? 'Сохранённый расчёт' :
    `Сохранённый расчёт от ${new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(value)}`;
}
