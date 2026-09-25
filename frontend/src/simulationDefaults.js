export const MODEL_START_SECONDS = 9 * 3600;
export const MODEL_START_WEEKDAY = 'MONDAY';

const COMMON_ZONES = ['Europe/Moscow', 'Asia/Yekaterinburg', 'Asia/Novosibirsk', 'Asia/Vladivostok', 'Asia/Sakhalin'];

export function validTimezone(value) {
  if (typeof value !== 'string' || !value.trim()) return false;
  try { new Intl.DateTimeFormat('ru-RU', { timeZone: value }).format(new Date()); return true; }
  catch { return false; }
}

export function modelTimezone(project, browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone) {
  const preferred = project?.profile?.timezone || project?.timezone;
  if (validTimezone(preferred)) return preferred;
  return validTimezone(browserZone) ? browserZone : '';
}

export function timezoneChoices(current = '') {
  return [...new Set([current, ...COMMON_ZONES].filter(validTimezone))];
}

export function formatModelClock(modelStart, simulationTimeUs) {
  if (!modelStart || !Number.isFinite(simulationTimeUs)) return null;
  const weekdays = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'];
  const elapsed = Math.max(0, Math.floor(simulationTimeUs / 1_000_000));
  const absolute = modelStart.seconds_from_midnight + elapsed;
  const weekday = weekdays[Math.floor(absolute / 86400) % 7];
  const secondOfDay = absolute % 86400;
  const hours = String(Math.floor(secondOfDay / 3600)).padStart(2, '0');
  const minutes = String(Math.floor(secondOfDay % 3600 / 60)).padStart(2, '0');
  return `${weekday}, ${hours}:${minutes} · ${modelStart.timezone}`;
}
