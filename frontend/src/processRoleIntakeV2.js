export const INTAKE_SCHEMA_VERSION = 'calculation-intake-v2';
export const NORMALIZATION_SCHEMA_VERSION = 'calculation-intake-normalization-v2';

const DEFINITIONS = [
  ['WAREHOUSE', 'warehouse_receiving_shipping', 'Приёмка и отгрузка', 'TRANSPORT_CYCLE', 'PALLET', 'pallet/day', ['forklift_driver', 'loader']],
  ['WAREHOUSE', 'warehouse_storage', 'Хранение', 'REFERENCE_ONLY', 'PALLET', 'pallet/day', ['storekeeper']],
  ['WAREHOUSE', 'warehouse_picking', 'Комплектация', 'REFERENCE_ONLY', 'PICK', 'pick/day', ['picker', 'sorter']],
  ['WAREHOUSE', 'warehouse_palletizing', 'Паллетизация', 'FIXED_CELL', 'PALLET', 'pallet/day', ['packer']],
  ['WAREHOUSE', 'warehouse_cleaning', 'Уборка', 'CLEANING_AREA', 'SQUARE_METER', 'm2/day', ['cleaner']],
  ['WAREHOUSE', 'warehouse_inventory', 'Инвентаризация', 'REFERENCE_ONLY', 'ITEM', 'item/day', ['inventory_worker']],
  ['AIRPORT', 'airport_baggage', 'Багаж', 'TRANSPORT_CYCLE', 'ITEM', 'item/day', ['baggage_handler']],
  ['AIRPORT', 'airport_catering', 'Бортовое питание', 'TRANSPORT_CYCLE', 'PORTION', 'portion/day', ['trolley_operator']],
  ['AIRPORT', 'airport_fuelling', 'Заправка', 'REFERENCE_ONLY', 'DELIVERY', 'delivery/day', ['special_equipment_driver']],
  ['AIRPORT', 'airport_internal_logistics', 'Внутренняя логистика', 'TRANSPORT_CYCLE', 'CART', 'cart/day', ['trolley_operator']],
  ['AIRPORT', 'airport_terminal_cleaning', 'Уборка терминала', 'CLEANING_AREA', 'SQUARE_METER', 'm2/day', ['terminal_cleaner']],
  ['AIRPORT', 'airport_apron_cleaning', 'Уборка перрона', 'CLEANING_AREA', 'SQUARE_METER', 'm2/day', ['perron_cleaner']],
  ['AIRPORT', 'airport_waste', 'Вывоз отходов', 'TRANSPORT_CYCLE', 'KILOGRAM', 'kg/day', ['trolley_operator']],
  ['AIRPORT', 'airport_inspection', 'Инспекция', 'REFERENCE_ONLY', 'ITEM', 'item/day', ['runway_inspector', 'security_guard']],
  ['AIRPORT', 'airport_passenger_assistance', 'Помощь пассажирам', 'REFERENCE_ONLY', 'DELIVERY', 'delivery/day', ['passenger_assistant', 'courier']],
  ['AIRPORT', 'airport_ground_service', 'Наземное обслуживание', 'REFERENCE_ONLY', 'DELIVERY', 'delivery/day', ['ramp_worker', 'ground_support_worker']],
  ['CLINIC', 'clinic_food', 'Доставка питания', 'DELIVERY_CYCLE', 'PORTION', 'portion/day', ['catering_worker']],
  ['CLINIC', 'clinic_linen', 'Транспорт белья', 'DELIVERY_CYCLE', 'KILOGRAM', 'kg/day', ['laundry_worker']],
  ['CLINIC', 'clinic_medicines', 'Доставка медикаментов', 'DELIVERY_CYCLE', 'DELIVERY', 'delivery/day', ['sanitary', 'porter']],
  ['CLINIC', 'clinic_biomaterials', 'Доставка биоматериалов', 'DELIVERY_CYCLE', 'SAMPLE', 'sample/day', ['lab_assistant']],
  ['CLINIC', 'clinic_sterile_sets', 'Стерильные наборы', 'DELIVERY_CYCLE', 'SET', 'set/day', ['sterile_supply_worker']],
  ['CLINIC', 'clinic_consumables', 'Расходные материалы', 'DELIVERY_CYCLE', 'ITEM', 'item/day', ['consumable_worker']],
  ['CLINIC', 'clinic_waste_a', 'Отходы класса А', 'DELIVERY_CYCLE', 'KILOGRAM', 'kg/day', ['sanitary', 'porter']],
  ['CLINIC', 'clinic_waste_b', 'Отходы класса Б', 'DELIVERY_CYCLE', 'KILOGRAM', 'kg/day', ['sanitary', 'porter']],
  ['CLINIC', 'clinic_results', 'Результаты анализов', 'DELIVERY_CYCLE', 'DELIVERY', 'delivery/day', ['lab_result_courier']],
  ['CLINIC', 'clinic_cleaning', 'Уборка помещений', 'CLEANING_AREA', 'SQUARE_METER', 'm2/day', ['cleaner']],
  ['CLINIC', 'clinic_inventory', 'Инвентаризация имущества', 'REFERENCE_ONLY', 'ITEM', 'item/day', ['inventory_worker']],
  ['CLINIC', 'clinic_safety_requirements', 'Требования безопасности', 'CONSTRAINT_ONLY', 'ITEM', 'item/day', []],
];

export const PROCESS_DEFINITIONS = Object.freeze(DEFINITIONS.map(
  ([objectKind, code, label, scope, quantityKind, unit, roles]) => Object.freeze({
    objectKind, code, label, scope, quantityKind, unit, roles: Object.freeze(roles),
  }),
));

export const OBJECT_KIND = Object.freeze({ retail: 'WAREHOUSE', airport: 'AIRPORT', clinic: 'CLINIC' });

export function definitionsFor(objectType) {
  const objectKind = OBJECT_KIND[objectType];
  return PROCESS_DEFINITIONS.filter((item) => item.objectKind === objectKind);
}

export function createDraft(objectType, sequence = 1) {
  const objectKind = OBJECT_KIND[objectType];
  if (!objectKind) throw new Error('UNSUPPORTED_OBJECT_KIND');
  const objectId = `draft.${objectKind.toLowerCase()}`;
  return {
    schemaVersion: INTAKE_SCHEMA_VERSION,
    revisionNumber: sequence,
    inputRevision: `draft.${sequence}`,
    objectId,
    objectKind,
    processes: definitionsFor(objectType).map((definition) => ({
      ...definition,
      blockId: `block.${definition.code}`,
      processId: `${objectId}.${definition.code}`,
      active: false,
      activationSource: 'USER',
      demand: '',
      shifts: '',
      hours: '',
      days: '',
      distance: '',
      batch: '',
      fieldSources: {},
    })),
    roles: [],
    overrideEvents: [],
  };
}

export function createWarehouseDemoDraft() {
  let draft = createDraft('retail');
  draft = updateProcess(draft, 'warehouse_receiving_shipping', {
    active: true, demand: '2000', shifts: '2', hours: '11', days: '365',
    distance: '120', batch: '1',
    fieldSources: {
      demand: 'ASSUMPTION', shifts: 'ASSUMPTION', hours: 'ASSUMPTION',
      days: 'ASSUMPTION', distance: 'ASSUMPTION', batch: 'ASSUMPTION',
    },
  });
  draft = setRoleActive(draft, 'warehouse_receiving_shipping', 'forklift_driver', true);
  return updateRole(draft, `${draft.objectId}.forklift_driver`, {
    headcount: '25', headcountSource: 'ASSUMPTION',
    salary: '120000', salarySource: 'ASSUMPTION', salaryConfirmed: false,
  });
}

export function createWarehouseFileDraft(normalized, imported) {
  if (normalized?.object_type !== 'retail' || normalized?.process_type !== 'transport') {
    throw new Error('Файл не описывает поддержанный складской транспортный процесс v2.');
  }
  const file = Object.values(imported?.parameter_provenance || {})[0]?.source;
  if (!/^[0-9a-f]{64}$/.test(file?.sha256 || '')) {
    throw new Error('У импортированного файла нет проверенной контрольной суммы.');
  }
  let draft = createDraft('retail');
  const fields = {
    demand: normalized.pallets_per_day, shifts: normalized.shifts_count,
    hours: normalized.shift_hours, days: normalized.operating_days,
    distance: normalized.avg_distance_m,
  };
  const patch = { active: true, activationSource: 'FILE', fileSource: { sha256: file.sha256, name: file.name }, fieldSources: {} };
  for (const [key, value] of Object.entries(fields)) {
    if (value != null && value !== '') { patch[key] = String(value); patch.fieldSources[key] = 'FILE'; }
  }
  draft = updateProcess(draft, 'warehouse_receiving_shipping', patch);
  draft = setRoleActive(draft, 'warehouse_receiving_shipping', 'forklift_driver', true);
  return updateRole(draft, `${draft.objectId}.forklift_driver`, {
    headcount: normalized.staff_headcount == null ? '' : String(normalized.staff_headcount),
    headcountSource: 'FILE', fileSource: { sha256: file.sha256, name: file.name },
    salary: '', salarySource: 'USER', salaryConfirmed: true,
  });
}

function revise(draft, patch) {
  const revisionNumber = draft.revisionNumber + 1;
  return { ...draft, ...patch, revisionNumber, inputRevision: `draft.${revisionNumber}` };
}

export function updateProcess(draft, processCode, patch) {
  return revise(draft, {
    processes: draft.processes.map((item) => {
      if (item.code !== processCode) return item;
      const fieldSources = { ...item.fieldSources };
      for (const key of ['demand', 'shifts', 'hours', 'days', 'distance', 'batch']) {
        if (Object.hasOwn(patch, key)) fieldSources[key] = 'USER';
      }
      return { ...item, ...patch, fieldSources: { ...fieldSources, ...(patch.fieldSources || {}) } };
    }),
  });
}

export function setRoleActive(draft, processCode, roleCode, active) {
  const process = draft.processes.find((item) => item.code === processCode);
  if (!process || !process.roles.includes(roleCode)) throw new Error('ROLE_NOT_ALLOWED_FOR_PROCESS');
  const roleId = `${draft.objectId}.${roleCode}`;
  const existing = draft.roles.find((item) => item.roleId === roleId);
  let roles;
  if (active && existing) {
    roles = draft.roles.map((item) => item.roleId === roleId
      ? { ...item, processIds: [...new Set([...item.processIds, process.processId])] }
      : item);
  } else if (active) {
    roles = [...draft.roles, { roleId, roleCode, processIds: [process.processId], headcount: '', headcountSource: 'USER', salary: '', salarySource: 'USER', salaryConfirmed: true }];
  } else if (existing) {
    roles = draft.roles
      .map((item) => item.roleId === roleId
        ? { ...item, processIds: item.processIds.filter((id) => id !== process.processId) }
        : item)
      .filter((item) => item.processIds.length > 0);
  } else {
    roles = draft.roles;
  }
  return revise(draft, { roles });
}

export function updateRole(draft, roleId, patch) {
  return revise(draft, {
    roles: draft.roles.map((item) => item.roleId === roleId ? { ...item, ...patch } : item),
  });
}

export function confirmRoleAssumption(draft, roleId) {
  const role = draft.roles.find((item) => item.roleId === roleId);
  if (!role || role.salarySource !== 'ASSUMPTION') throw new Error('ROLE_ASSUMPTION_NOT_FOUND');
  const revisionNumber = draft.revisionNumber + 1;
  const inputRevision = `draft.${revisionNumber}`;
  return {
    ...draft,
    revisionNumber,
    inputRevision,
    roles: draft.roles.map((item) => item.roleId === roleId ? { ...item, salaryConfirmed: true } : item),
    overrideEvents: [...draft.overrideEvents, {
      eventId: `override.${revisionNumber}.${roleId}`,
      field: `${roleId}.monthly_gross_salary`,
      action: 'CONFIRM_ASSUMPTION',
      inputRevision,
    }],
  };
}

const DECIMAL_PATTERN = /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/;
const positive = (value) => value !== '' && DECIMAL_PATTERN.test(String(value)) && Number(value) > 0;
const nonNegative = (value) => value !== '' && DECIMAL_PATTERN.test(String(value));

export function validateDraft(draft) {
  const issues = [];
  for (const process of draft.processes) {
    if (!process.active) continue;
    if (!positive(process.demand)) issues.push({ severity: 'BLOCKER', code: 'DEMAND_REQUIRED', ref: `${process.code}.demand` });
    if (!positive(process.shifts) || !positive(process.hours) || !positive(process.days)) {
      issues.push({ severity: 'BLOCKER', code: 'SCHEDULE_REQUIRED', ref: `${process.code}.schedule` });
    } else if (Number(process.shifts) * Number(process.hours) > 24) {
      issues.push({ severity: 'BLOCKER', code: 'SCHEDULE_OVER_24H', ref: `${process.code}.schedule` });
    }
    const assigned = draft.roles.filter((role) => role.processIds.includes(process.processId));
    if (assigned.length === 0) issues.push({ severity: 'INFO', code: 'NO_FOT_BENEFIT', ref: process.code });
  }
  for (const role of draft.roles) {
    if (!positive(role.headcount)) issues.push({ severity: 'BLOCKER', code: 'HEADCOUNT_REQUIRED', ref: `${role.roleId}.headcount` });
    if (!nonNegative(role.salary)) issues.push({ severity: 'REQUIRED_FOR_LABOUR', code: 'SALARY_REQUIRED', ref: `${role.roleId}.salary` });
    if (role.salarySource === 'ASSUMPTION' && !role.salaryConfirmed) issues.push({ severity: 'BLOCKER', code: 'ASSUMPTION_CONFIRMATION_REQUIRED', ref: `${role.roleId}.salary` });
  }
  return issues;
}

function provenance(value, source = 'USER', confirmed = false, fileSource = null) {
  return { source, raw_text: String(value), user_confirmed: source === 'USER' || confirmed,
    ...(source === 'FILE' ? { file_sha256: fileSource?.sha256, file_name: fileSource?.name } : {}) };
}

function quantity(value, unit, source = 'USER', confirmed = false, fileSource = null) {
  if (value === '' || value == null) return null;
  return { value: String(value), unit, provenance: provenance(value, source, confirmed, fileSource) };
}

export function serializeDraft(draft) {
  const blockers = validateDraft(draft).filter((item) => item.severity === 'BLOCKER');
  if (blockers.length) throw new Error('INTAKE_DRAFT_INVALID');
  return {
    schema_version: INTAKE_SCHEMA_VERSION,
    input_revision: draft.inputRevision,
    object_id: draft.objectId,
    object_kind: draft.objectKind,
    processes: draft.processes.map((process) => ({
      block_id: process.blockId,
      process_id: process.processId,
      process_code: process.code,
      active: process.active,
      activation_source: process.activationSource,
      quantity_kind: process.quantityKind,
      demand: quantity(process.demand, process.unit, process.fieldSources?.demand || 'USER', false, process.fileSource),
      schedule: process.shifts !== '' || process.hours !== '' || process.days !== '' ? {
        shifts_per_day: quantity(process.shifts, 'shift', process.fieldSources?.shifts || 'USER', false, process.fileSource),
        shift_hours: quantity(process.hours, 'h', process.fieldSources?.hours || 'USER', false, process.fileSource),
        days_per_year: quantity(process.days, 'day', process.fieldSources?.days || 'USER', false, process.fileSource),
      } : null,
      route_distance: quantity(process.distance, 'm', process.fieldSources?.distance || 'USER', false, process.fileSource),
      explicit_batch: quantity(process.batch, 'unit/trip', process.fieldSources?.batch || 'USER', false, process.fileSource),
      role_refs: draft.roles.filter((role) => role.processIds.includes(process.processId)).map((role) => role.roleId),
    })),
    roles: draft.roles.map((role) => ({
      role_id: role.roleId,
      object_scope: draft.objectKind,
      role_code: role.roleCode,
      headcount: quantity(role.headcount, 'person', role.headcountSource || 'USER', false, role.fileSource),
      monthly_gross_salary: quantity(role.salary, 'RUB/person/month', role.salarySource, role.salaryConfirmed, role.fileSource),
      zero_cost_marker: nonNegative(role.salary) && Number(role.salary) === 0 ? 'ZERO_COST_ROLE' : null,
      process_ids: role.processIds,
    })),
  };
}

export function createNormalizationClient(fetchImpl, endpoint = '/api/v2/calculation-intake/normalize', getCurrentRevision = null) {
  let requestSequence = 0;
  return async (draft) => {
    requestSequence += 1;
    const current = requestSequence;
    const request = serializeDraft(draft);
    const response = await fetchImpl(endpoint, {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || 'INTAKE_NORMALIZATION_FAILED');
    const latestRevision = getCurrentRevision?.();
    if (current !== requestSequence || payload.input_revision !== draft.inputRevision || (latestRevision && latestRevision !== draft.inputRevision)) {
      const error = new Error('STALE_INTAKE_RESPONSE');
      error.code = 'STALE_INTAKE_RESPONSE';
      throw error;
    }
    if (payload.schema_version !== NORMALIZATION_SCHEMA_VERSION) throw new Error('UNKNOWN_NORMALIZATION_SCHEMA');
    return { request, response: payload };
  };
}
