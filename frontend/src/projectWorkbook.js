import { createDraft, definitionsFor } from './processRoleIntakeV2.js';
const DEMAND_KINDS = { 'pallet/day': 'PALLET', 'box/day': 'BOX', 'case/day': 'CASE', 'cart/day': 'CART',
  'delivery/day': 'DELIVERY', 'portion/day': 'PORTION', 'kg/day': 'KILOGRAM', 'sample/day': 'SAMPLE',
  'set/day': 'SET', 'bin/day': 'BIN', 'item/day': 'ITEM', 'm2/day': 'SQUARE_METER', 'pick/day': 'PICK' };

export function workbookDraft(input) {
  const draft = createDraft(input.object_type);
  const records = input.records;
  const source = input.file_source;
  const value = (row, key) => String(row[key]?.value ?? '');
  const object = records['Объект']?.main || {};
  draft.facility = { name: value(object, 'name'), totalArea: value(object, 'total_area_m2'),
    activeArea: value(object, 'active_area_m2'), fileSource: source,
    fieldSources: {
      totalArea: object.total_area_m2?.status === 'ASSUMPTION' ? 'ASSUMPTION' : 'FILE',
      activeArea: object.active_area_m2?.status === 'ASSUMPTION' ? 'ASSUMPTION' : 'FILE',
    }, fieldConfirmations: { totalArea: false, activeArea: false } };
  draft.zones = Object.entries(records['Зоны']).map(([id, row]) => ({
    zoneId: `zone.${draft.objectId}.${id}`, label: value(row, 'label'), constraints: value(row, 'constraints'),
  }));
  const ids = {};
  draft.processes = Object.entries(records['Процессы']).map(([id, row]) => {
    const definition = definitionsFor(input.object_type).find((item) => item.code === value(row, 'process_code'));
    const zoneId = `zone.${draft.objectId}.${value(row, 'zone_id')}`;
    const processId = `${zoneId}.${id}`;
    ids[id] = processId;
    const process = { ...definition, zoneId, processId, blockId: `block.${processId}`, active: value(row, 'active') === 'YES',
      activationSource: 'FILE', fileSource: source, fieldSources: {}, fieldConfirmations: {},
      exchangeSeconds: value(row, 'exchange_seconds'), cleaningFrequency: value(row, 'cleaning_frequency') };
    process.unit = row.demand.unit;
    process.quantityKind = process.unit === definition.unit ? definition.quantityKind
      : definition.code === 'clinic_results' && process.unit === 'item/day' ? 'DIGITAL_FLOW' : DEMAND_KINDS[process.unit];
    for (const field of ['demand', 'shifts', 'hours', 'days', 'distance', 'batch']) {
      process[field] = value(row, field);
      process.fieldSources[field] = row[field]?.status === 'ASSUMPTION' ? 'ASSUMPTION' : 'FILE';
      process.fieldConfirmations[field] = false;
    }
    return process;
  });
  draft.roles = Object.entries(records['Роли']).map(([, row]) => ({
    roleId: `${draft.objectId}.${value(row, 'role_code')}`, roleCode: value(row, 'role_code'),
    processIds: value(row, 'process_ids').split(',').map((id) => ids[id.trim()]).filter(Boolean),
    headcount: value(row, 'headcount'), salary: value(row, 'salary'),
    headcountSource: row.headcount.status === 'ASSUMPTION' ? 'ASSUMPTION' : 'FILE',
    salarySource: row.salary.status === 'ASSUMPTION' ? 'ASSUMPTION' : 'FILE', salaryConfirmed: false, fileSource: source,
  }));
  draft.importPending = true;
  return draft;
}

export function confirmWorkbookDraft(draft) {
  return { ...draft, importPending: false, revisionNumber: draft.revisionNumber + 1, inputRevision: `draft.${draft.revisionNumber + 1}`,
    facility: { ...draft.facility, fieldConfirmations: { totalArea: true, activeArea: true } },
    processes: draft.processes.map((process) => ({ ...process, fieldConfirmations: Object.fromEntries(Object.keys(process.fieldSources).map((key) => [key, true])) })),
    roles: draft.roles.map((role) => ({ ...role, salaryConfirmed: true, headcountConfirmed: true })) };
}

export function workbookEconomics(input) {
  if (!input?.records) return undefined;
  const result = { field_sources: {}, assumption_evidence: {} };
  const rows = input.records['Экономика'].main;
  const date = rows.evaluation_date.value || new Date().toISOString().slice(0, 10);
  for (const [code, row] of Object.entries(rows)) {
    if (row.value == null || row.unit === 'YES/NO') continue;
    result[code] = row.value;
    if (!['evaluation_date', 'raas_infrastructure_owner', 'currency', 'vat_basis'].includes(code)) {
      result.field_sources[code] = 'ASSUMPTION';
      result.assumption_evidence[code] = { schema_version: 'scenario-assumption-evidence-v1', template_id: null,
        version: 'custom-v1', source: 'USER', rationale: `${input.file_source.name}; SHA256 ${input.file_source.sha256}; ${row.status}: ${row.source}`,
        published_on: date, confirmed_value: row.value, confirmed: false };
    }
  }
  result.timezone = input.records['Объект'].main.timezone.value || '';
  result.start_seconds_from_midnight = rows.start_seconds_from_midnight.value ?? '';
  const optional = (code) => rows[code]?.value || '';
  const policy = ['robots_per_control_post', 'robots_per_day_technician', 'rotation_factor'];
  if (policy.every(optional)) {
    result.staffing_policy = { schema_version: 'staffing-policy-v2',
      robots_per_control_post: optional('robots_per_control_post'),
      robots_per_day_technician: optional('robots_per_day_technician'),
      rotation_factor: optional('rotation_factor'),
      technician_presence: optional('technician_presence') || 'DAY_WORKLOAD',
      source: 'ASSUMPTION', provenance_ref: `workbook:${input.file_source.sha256}` };
  }
  if (optional('robotizable_share') && optional('residual_operations')) {
    result.work_share = { schema_version: 'robotizable-work-share-v1',
      fraction: optional('robotizable_share'), residual_operations: optional('residual_operations'),
      source: 'ASSUMPTION', provenance_ref: `workbook:${input.file_source.sha256}` };
  }
  if (optional('control_mode') && optional('technician_purchase_mode')) {
    result.staffing_purchase = { control_mode: optional('control_mode'),
      technician_mode: optional('technician_purchase_mode') };
  }
  if (optional('control_mode') && optional('technician_raas_mode')) {
    result.staffing_raas = { control_mode: optional('control_mode'),
      technician_mode: optional('technician_raas_mode') };
  }
  // Workbook YES is a proposal. Qualification and contract confirmations still
  // require an explicit click in the application before a saved calculation.
  result.schema_version = 'economics-explicit-inputs-v6';
  return result;
}
