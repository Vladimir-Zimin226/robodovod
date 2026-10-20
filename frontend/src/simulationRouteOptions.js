const TRANSPORT_ROLES = new Set(['forklift_driver', 'loader', 'picker', 'storekeeper']);
const TRANSPORT_PROCESSES = new Set(['warehouse_receiving_shipping', 'warehouse_storage',
  'airport_baggage', 'airport_internal_logistics', 'clinic_medicines']);

export function simulationOptions(input, report) {
  if (!input || !report) return [];
  if (report.kind) return input.roles.flatMap((role, roleIndex) => role.works
    .map((work, workIndex) => ({ roleIndex, workIndex, key: `${roleIndex}:${workIndex}`,
      label: `${report.roles[roleIndex]?.label || role.role_code}: ${work.technical_task}`,
      processCode: work.process_code }))
    .filter((item) => TRANSPORT_PROCESSES.has(item.processCode)));
  return input.roles.map((role, roleIndex) => ({ roleIndex, key: `${roleIndex}`,
    label: report.roles[roleIndex]?.label || role.role_code }))
    .filter((item) => TRANSPORT_ROLES.has(input.roles[item.roleIndex].role_code));
}
