// Scenario estimates for typical objects. These are not organizer measurements.
// Keep the review table in data/role-work/role-process-measurement-template-v1.csv in sync.
export const ROLE_WORK_SCENARIOS = Object.freeze({
  warehouse_receiving_shipping: Object.freeze({
    forklift_driver: Object.freeze({
      id: 'RW-WH-FORKLIFT-01', headcount: '25', monthlyEmployerCost: '156240',
      manualUnitsPerShift: '100', robotizableFraction: '0.8',
      residualOperations: 'Ручная приёмка, проверка и нестандартные паллеты остаются у оператора.',
      basis: 'RW-WH-FORKLIFT-01: сценарий 100 паллет/смену, 480 из 600 минут типовой работы заменяемы; не замер.',
    }),
    loader: Object.freeze({
      id: 'RW-WH-LOADER-01', headcount: '8', monthlyEmployerCost: '104160',
      manualUnitsPerShift: '250', robotizableFraction: '0.25',
      residualOperations: 'Погрузка, крепление, сканирование, приёмка и исключения остаются у грузчика.',
      basis: 'RW-WH-LOADER-01: сценарий 8 человек на 2000 паллет/сутки, 150 из 600 минут заменяемы; не замер.',
    }),
  }),
  airport_terminal_cleaning: Object.freeze({
    terminal_cleaner: Object.freeze({
      id: 'RW-AP-CLEANER-01', headcount: '30', monthlyEmployerCost: '84630',
      manualUnitsPerShift: '1700', robotizableFraction: '0.6',
      residualOperations: 'Кромки, лестницы, загрязнения вне маршрута и санитарная обработка остаются вручную.',
      basis: 'RW-AP-CLEANER-01: сценарий 30 из 180 работников терминала, 51000 м²/сутки, 252 из 420 минут заменяемы; не замер.',
    }),
  }),
  clinic_food: Object.freeze({
    catering_worker: Object.freeze({
      id: 'RW-CL-FOOD-01', headcount: '6', monthlyEmployerCost: '67704',
      manualUnitsPerShift: '325', robotizableFraction: '0.4',
      residualOperations: 'Приготовление, загрузка тележки, раздача, контроль питания и санитарная проверка остаются вручную.',
      basis: 'RW-CL-FOOD-01: сценарий 6 из 28 сотрудников пищеблока, 1950 порций/сутки, 168 из 420 минут заменяемы; не замер.',
    }),
  }),
});

export function applyRoleWorkScenario(values, capacityRequest) {
  const processCode = capacityRequest?.process?.process_code;
  const scenario = ROLE_WORK_SCENARIOS[processCode];
  const roleRefs = capacityRequest?.process?.role_refs || [];
  const roles = capacityRequest?.role_pool?.roles || [];
  if (!scenario || !roleRefs.length) return values;
  const matched = roleRefs.map((roleId) => ({ roleId, role: roles.find((item) => item.role_id === roleId) }))
    .filter(({ role }) => role && scenario[role.role_code]
      && String(role.headcount?.normalized_value) === scenario[role.role_code].headcount);
  if (matched.length !== roleRefs.length) return values;
  const primary = matched[0];
  const primaryData = scenario[primary.role.role_code];
  const profiles = Object.fromEntries(matched.map(({ roleId, role }) => {
    const row = scenario[role.role_code];
    return [roleId, { fraction: row.robotizableFraction, manual: row.manualUnitsPerShift,
      residual: row.residualOperations, source: 'ASSUMPTION', basis: row.basis, confirmed: true }];
  }));
  return { ...values, primaryRoleId: primary.roleId,
    manualUnitsPerShift: primaryData.manualUnitsPerShift,
    robotizableShare: primaryData.robotizableFraction,
    residualOperations: primaryData.residualOperations,
    roleWorkProfiles: { ...values.roleWorkProfiles, ...profiles },
    sources: { ...values.sources, manual_units_per_shift: 'ASSUMPTION' },
    assumptions: { ...values.assumptions, manual_units_per_shift: {
      schema_version: 'scenario-assumption-evidence-v1', template_id: null,
      version: 'role-work-scenario-v1', source: 'USER', rationale: primaryData.basis,
      published_on: '2026-10-19', confirmed_value: primaryData.manualUnitsPerShift, confirmed: true,
    } },
  };
}
