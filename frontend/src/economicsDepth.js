export const ECONOMICS_DEPTHS = Object.freeze([
  { code: 'BASIC', label: 'Базовый', groups: ['Труд'], description: 'Выработка, штат и изменение затрат на труд. Денежные ветки покупки и аренды без их входов не рассчитываются.' },
  { code: 'ADVANCED', label: 'Углублённый', groups: ['Покупка'], description: 'Добавляет покупку: вложения, эксплуатацию, NPV, ROI и окупаемость по действующим формулам.' },
  { code: 'FULL', label: 'Полный', groups: ['RaaS', 'Визуализация'], description: 'Добавляет аренду и сравнение с покупкой, уточнение цены и графика. Все коммерческие условия требуют данных или явных допущений.' },
]);
export const depthIndex = (code) => Math.max(0, ECONOMICS_DEPTHS.findIndex((item) => item.code === code));
export const depthLabel = (code) => ECONOMICS_DEPTHS.find((item) => item.code === code)?.label || 'Не указан в историческом расчёте';

// Higher-level fields remain in the editor, but do not enter a lower-level run.
export function valuesAtDepth(values, fields) {
  const selected = depthIndex(values.calculationDepth);
  const next = { ...values, sources: { ...values.sources }, assumptions: { ...values.assumptions } };
  for (const [group, key, server] of fields) {
    if (ECONOMICS_DEPTHS.findIndex((item) => item.groups.includes(group)) > selected && group !== 'Визуализация') {
      next[key] = ''; delete next.sources[server]; delete next.assumptions[server];
    }
  }
  if (selected < 2) Object.assign(next, { raasInfrastructureOwner: '', raasScopeConfirm: false,
    technicianRaasMode: '', purchasePriceOverride: '', purchasePriceSource: '' });
  if (selected < 1) Object.assign(next, { currencyConfirm: false, initialBatteryConfirm: false, batteryServiceConfirm: false });
  return next;
}
