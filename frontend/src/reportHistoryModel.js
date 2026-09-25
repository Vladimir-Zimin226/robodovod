export const REPORT_BRANCHES = [
  ['capacity', 'Парк'], ['labour', 'Труд'], ['purchase', 'Покупка'],
  ['raas', 'RaaS'], ['simulation', 'Симуляция'],
];

const PROCESS_NAMES = {
  warehouse_receiving_shipping: 'Приёмка и отгрузка',
  transport: 'Перемещение грузов', cleaning: 'Уборка', palletizing: 'Паллетизация',
};

export function processName(summary) {
  return PROCESS_NAMES[summary?.process_code] || summary?.process_code?.replaceAll('_', ' ') || summary?.process_id || 'Процесс не указан';
}

export function reportType(run) {
  if (run.status === 'FAILED') return 'Ошибка расчёта';
  if (run.status === 'CANCELLED') return 'Расчёт отменён';
  if (run.status === 'PENDING' || run.status === 'RUNNING') return 'Расчёт выполняется';
  if (run.run_kind === 'CAPACITY_ANALYSIS') return 'Технический · частичный';
  if (run.report_summary?.result_type === 'PARTIAL') return 'Частичный';
  return run.report_summary?.result_type === 'FULL' ? 'Полный' : 'Статус не указан';
}

export function branchAvailability(summary, key) {
  const status = summary?.branches?.[key];
  if (status === 'SAVED') return 'Сохранена';
  if (status === 'CALCULATED') return 'Рассчитано';
  if (status === 'UNKNOWN') return 'Нет данных о ветке';
  return key === 'simulation' ? 'Не сохранена' : 'Не рассчитано';
}

export function baseNpv(summary, acquisition) {
  return summary?.npv?.find((item) => item.acquisition === acquisition && item.uncertainty === 'BASE')?.value ?? null;
}

export function groupProjectRuns(runs) {
  const groups = new Map();
  for (const run of runs) {
    const id = run.report_summary?.group_run_id || run.id;
    if (!groups.has(id)) groups.set(id, { id, runs: [] });
    groups.get(id).runs.push(run);
  }
  return [...groups.values()].map((group) => ({
    ...group,
    runs: group.runs.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
  })).sort((a, b) => Date.parse(b.runs[0]?.created_at) - Date.parse(a.runs[0]?.created_at));
}

export function comparisonRows(left, right) {
  if (left.project_id !== right.project_id || left.report_summary?.group_run_id !== right.report_summary?.group_run_id) {
    throw new TypeError('Можно сравнить только версии одной операции проекта');
  }
  return [
    { label: 'Тип результата', left: reportType(left), right: reportType(right) },
    { label: 'Технический парк', left: left.report_summary?.fleet, right: right.report_summary?.fleet, unit: 'роботов' },
    ...REPORT_BRANCHES.map(([key, label]) => ({ label, left: branchAvailability(left.report_summary, key), right: branchAvailability(right.report_summary, key) })),
    { label: 'NPV покупки · базовый сценарий', left: baseNpv(left.report_summary, 'PURCHASE'), right: baseNpv(right.report_summary, 'PURCHASE'), unit: '₽' },
    { label: 'NPV RaaS · базовый сценарий', left: baseNpv(left.report_summary, 'RAAS'), right: baseNpv(right.report_summary, 'RAAS'), unit: '₽' },
  ];
}
