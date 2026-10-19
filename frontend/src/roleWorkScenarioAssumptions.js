import scenarioData from './roleWorkScenarioData.json' with { type: 'json' };

// Only rows with an executable C11 process and no unresolved safety gate are
// offered by the economics button. All 35 rows remain visible in the CSV.
export const ROLE_WORK_SCENARIO_ROWS = Object.freeze(scenarioData.records);
export const ROLE_WORK_SCENARIOS = Object.freeze(Object.fromEntries(
  [...new Set(ROLE_WORK_SCENARIO_ROWS.filter((row) => row.calculation_status === 'CALCULABLE')
    .map((row) => row.process_code))].map((processCode) => [processCode, Object.freeze(Object.fromEntries(
    ROLE_WORK_SCENARIO_ROWS.filter((row) => row.process_code === processCode && row.calculation_status === 'CALCULABLE')
      .map((row) => [row.role_code, Object.freeze({
        id: row.evidence_ref,
        headcount: String(Number(row.object_role_headcount) * Number(row.process_allocation_fraction)),
        monthlyEmployerCost: row.monthly_amount_rub_per_person,
        manualUnitsPerShift: row.manual_units_per_person_shift,
        robotizableFraction: row.robotizable_fraction,
        residualOperations: row.residual_operations,
        basis: row.work_basis,
      })]),
  ))]),
));

export function applyRoleWorkScenario(values, capacityRequest) {
  const processCode = capacityRequest?.process?.process_code;
  const scenario = ROLE_WORK_SCENARIOS[processCode];
  const roleRefs = capacityRequest?.process?.role_refs || [];
  const roles = capacityRequest?.role_pool?.roles || [];
  if (!scenario || !roleRefs.length) return values;
  const matched = roleRefs.map((roleId) => ({ roleId, role: roles.find((item) => item.role_id === roleId) }))
    .filter(({ role }) => role && scenario[role.role_code]
      && String(role.headcount?.normalized_value) === scenario[role.role_code].headcount
      && (!role.process_ids || role.process_ids.length === 1));
  if (matched.length !== roleRefs.length) return values;
  const primary = matched.find(({ role }) => role.role_code === 'forklift_driver') || matched[0];
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
