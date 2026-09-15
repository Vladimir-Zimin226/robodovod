import { DEFAULT_CONFIG, normalizeConfig } from './config.js';

function textSeed(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `SPEC-${(hash >>> 0).toString(36).toUpperCase()}`;
}

function firstNumber(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return Number(match[1]);
  }
  return null;
}

function detectTemplate(text) {
  const scores = {
    warehouse: ['склад', 'стеллаж', 'паллет', 'комплектов', 'логистическ', 'распределительн'],
    airport: ['аэропорт', 'терминал', 'багаж', 'пассажир', 'регистрац', 'посадк', 'выход'],
    hospital: ['больниц', 'клиник', 'палат', 'пациент', 'медицин', 'аптек', 'расходник']
  };
  const ranked = Object.entries(scores).map(([template, words]) => ({
    template,
    score: words.reduce((sum, word) => sum + (text.includes(word) ? 1 : 0), 0)
  })).sort((a, b) => b.score - a.score);
  return ranked[0].score ? ranked[0] : { template: null, score: 0 };
}

export function parseWorldDescription(description, base = DEFAULT_CONFIG) {
  const raw = String(description || '').trim();
  const text = raw.toLocaleLowerCase('ru-RU').replace(/ё/g, 'е');
  const detected = detectTemplate(text);
  const values = { ...base, template: detected.template || base.template, seed: raw ? textSeed(text) : base.seed };
  const recognized = [];
  const assumptions = [];

  if (detected.score) recognized.push(`тип объекта: ${detected.template === 'warehouse' ? 'склад' : detected.template === 'airport' ? 'аэропорт' : 'больница'}`);
  else assumptions.push('тип объекта не найден — сохранён выбор формы');

  const dimensions = text.match(/(\d{2,3})\s*(?:м|метр(?:а|ов)?)?\s*[xх×*]\s*(\d{2,3})\s*(?:м|метр(?:а|ов)?)?/i) ||
    text.match(/(?:размер(?:ом|ы)?|габарит(?:ом|ы)?)\D{0,12}(\d{2,3})\s*(?:на)\s*(\d{2,3})/i);
  if (dimensions) {
    values.width = Number(dimensions[1]);
    values.depth = Number(dimensions[2]);
    recognized.push(`размер: ${values.width} × ${values.depth} м`);
  } else {
    const width = firstNumber(text, [/(?:ширин[а-я]*|по ширине)\D{0,10}(\d{2,3})/i]);
    const depth = firstNumber(text, [/(?:глубин[а-я]*|длин[а-я]*|по длине)\D{0,10}(\d{2,3})/i]);
    if (width) { values.width = width; recognized.push(`ширина: ${width} м`); }
    if (depth) { values.depth = depth; recognized.push(`глубина: ${depth} м`); }
    if (!width || !depth) assumptions.push('часть габаритов взята из значений формы');
  }

  const robots = firstNumber(text, [/(\d{1,2})\s*(?:[а-я-]+\s+){0,2}(?:amr|амр|робот[а-я]*)/i, /(?:парк|количество)\D{0,10}(\d{1,2})\s*(?:amr|амр|робот[а-я]*)?/i]);
  if (robots) { values.robotCount = robots; recognized.push(`роботы: ${robots}`); }
  else assumptions.push(`парк: ${base.robotCount} AMR`);

  const template = values.template;
  const unitsPatterns = template === 'hospital'
    ? [/(\d{1,2})\s*палат/i, /палат[а-я]*\D{0,8}(\d{1,2})/i]
    : template === 'airport'
      ? [/(\d{1,2})\s*(?:выход|гейт)[а-я]*/i, /(?:выход|гейт)[а-я]*\D{0,8}(\d{1,2})/i]
      : [/(\d{1,2})\s*(?:ряд|лини)[а-я]*/i, /(?:ряд|лини)[а-я]*\D{0,8}(\d{1,2})/i];
  const units = firstNumber(text, unitsPatterns);
  if (units) {
    values.rackRows = units;
    recognized.push(`${template === 'hospital' ? 'палаты в крыле' : template === 'airport' ? 'выходы' : 'ряды'}: ${units}`);
  } else assumptions.push('планировочные единицы взяты из формы');

  const occupancy = firstNumber(text, [/(\d{2,3})\s*%\s*(?:загруз|занят|заполн|поток)?/i, /(?:загруз|занят|заполн)[а-я]*\D{0,10}(\d{2,3})\s*%/i]);
  if (occupancy) { values.occupancy = occupancy; recognized.push(`загрузка: ${occupancy}%`); }
  else assumptions.push(`загрузка: ${base.occupancy}%`);

  const config = normalizeConfig(values);
  const corrections = [];
  const parameterNames = { width: 'ширина', depth: 'глубина', rackRows: 'планировочные единицы', robotCount: 'число роботов', occupancy: 'загрузка' };
  for (const key of ['width', 'depth', 'rackRows', 'robotCount', 'occupancy']) {
    if (Number(values[key]) !== config[key]) corrections.push(`${parameterNames[key]}: ограничено до ${config[key]}`);
  }
  return {
    config,
    recognized,
    assumptions: [...assumptions, ...corrections],
    confidence: raw ? Math.min(1, (recognized.length + detected.score) / 8) : 0,
    source: raw
  };
}
