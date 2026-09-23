const ROOT_FIELDS = new Set(['schema_version', 'revision_id', 'source', 'template', 'seed', 'presentation', 'facility', 'zones', 'fleet', 'task_profiles', 'economics', 'assumptions', 'warnings']);
const ZONE_FIELDS = new Set(['id', 'name', 'process_type', 'cargo_type', 'status', 'demand_per_day', 'avg_distance_m', 'aisle_width_m', 'polygon']);
const FLEET_FIELDS = new Set(['zone_id', 'equipment_model_id', 'visual_profile', 'quantity', 'max_speed_m_s', 'payload_kg']);
const TASK_FIELDS = new Set(['zone_id', 'kind', 'demand_per_day', 'units_per_trip', 'exchange_time_s']);
const PRESENTATION_FIELDS = new Set(['autoplay', 'default_camera_mode', 'manual_control_available', 'editor_available']);
const FACILITY_FIELDS = new Set(['area_m2', 'width_m', 'depth_m', 'geometry_status', 'occupancy_percent']);
const ECONOMICS_FIELDS = new Set(['scenario', 'horizon_years', 'capex_rub', 'annual_opex_rub', 'annual_savings_rub', 'payback_years', 'npv_rub', 'tco_rub', 'fte_released', 'confidence', 'status']);
const ASSUMPTION_FIELDS = new Set(['code', 'message']);
const V2_ROOT_FIELDS = new Set(['schema_version', 'revision_id', 'source', 'template', 'seed', 'analysis', 'versions', 'profile', 'operating_windows', 'zones', 'routes', 'fleet', 'tasks', 'finance', 'assumptions', 'trace_node_refs', 'warnings']);
const V2_ANALYSIS_FIELDS = new Set(['project_id', 'tenant_id', 'capacity_run_id', 'input_revision', 'capacity_request_digest', 'capacity_result_digest', 'capacity_trace_digest']);
const V2_VERSION_FIELDS = new Set(['scenario_contract_version', 'scenario_policy_version', 'capacity_result_version', 'capacity_trace_version', 'calculation']);
const V2_CALCULATION_VERSION_FIELDS = new Set(['catalog_version_id', 'catalog_content_digest', 'capacity_projection_version', 'capacity_projection_digest', 'registry_version', 'registry_digest', 'process_catalog_version', 'formula_bundle_version', 'constraint_rules_version', 'commercial_policy_version', 'precision_policy_version', 'calculation_policy_version']);
const V2_PROFILE_FIELDS = new Set(['process_id', 'process_code', 'process_scope', 'calculation_profile', 'quantity_kind', 'capacity_status']);
const V2_WINDOW_FIELDS = new Set(['window_id', 'start_time', 'duration', 'timezone', 'source', 'provenance_ref']);
const V2_ZONE_FIELDS = new Set(['zone_id', 'label', 'geometry_source', 'geometry_ref', 'assumption_ref']);
const V2_ROUTE_FIELDS = new Set(['route_id', 'geometry_source', 'one_way_distance', 'geometry_ref', 'assumption_ref']);
const V2_FLEET_FIELDS = new Set(['fleet_id', 'zone_id', 'process_id', 'model_id', 'position_id', 'selected_fleet', 'recommended_fleet', 'nominal_capacity', 'effective_capacity', 'coverage', 'raw_load_ratio', 'utilization', 'overloaded']);
const V2_TASK_FIELDS = new Set(['task_id', 'zone_id', 'process_id', 'demand', 'operating_window_refs', 'exchange', 'batch', 'route_ref']);
const V2_EXCHANGE_FIELDS = new Set(['mode', 'total_time', 'load_time', 'unload_time']);
const V2_BATCH_FIELDS = new Set(['semantics', 'units_per_cycle', 'provenance_ref']);
const V2_QUANTITY_FIELDS = new Set(['value', 'unit', 'quantity_kind', 'numeric_encoding']);
const V2_ASSUMPTION_FIELDS = new Set(['assumption_id', 'version', 'provenance_ref', 'scope', 'message']);
const V2_PROCESS = Object.freeze({
  TRANSPORT_CYCLE_V1: { processType: 'transport', taskKind: 'box_move', internalProfile: 'cargo-amr', speed: .8 },
  DELIVERY_CYCLE_V1: { processType: 'delivery', taskKind: 'delivery', internalProfile: 'medical-cart', speed: .65 },
  CLEANING_AREA_V1: { processType: 'cleaning', taskKind: 'cleaning', internalProfile: 'cleaning-robot', speed: .55 },
  PALLETIZING_CELL_V1: { processType: 'palletizing', taskKind: 'palletizing', internalProfile: 'palletizer-cell', speed: 0 }
});
const VISUAL_PROFILE_MAP = Object.freeze({
  'pallet-amr': 'pallet-amr', 'cargo-amr': 'cargo-amr', tugger: 'tow-amr',
  'medical-delivery': 'medical-cart', 'service-delivery': 'service-robot',
  'service-cleaner': 'cleaning-robot', 'industrial-cleaner': 'cleaning-robot',
  'palletizer-cell': 'palletizer-cell'
});
const PROCESS_TASK_KINDS = Object.freeze({
  transport: new Set(['pallet_move', 'box_move', 'cart_move']), delivery: new Set(['delivery']),
  cleaning: new Set(['cleaning']), palletizing: new Set(['palletizing'])
});

function assertObject(value, path) { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError(`${path} должен быть объектом`); }
function rejectUnknown(value, allowed, path) { assertObject(value, path); const unknown = Object.keys(value).filter(key => !allowed.has(key)); if (unknown.length) throw new TypeError(`${path}: неизвестные поля: ${unknown.join(', ')}`); }
function positiveNumber(value, path, allowZero = false) { if (!Number.isFinite(value) || (allowZero ? value < 0 : value <= 0)) throw new TypeError(`${path} должен быть ${allowZero ? 'неотрицательным' : 'положительным'} числом`); return value; }
function positiveInteger(value, path, maximum = Number.MAX_SAFE_INTEGER) { if (!Number.isInteger(value) || value < 1 || value > maximum) throw new TypeError(`${path} должен быть целым числом 1…${maximum}`); return value; }
function deepFreeze(value) { if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value; Object.values(value).forEach(deepFreeze); return Object.freeze(value); }
const clone = value => JSON.parse(JSON.stringify(value));

function validateRoot(source) {
  rejectUnknown(source, ROOT_FIELDS, 'ScenarioSpec');
  if (source.schema_version !== 'scenario-spec-v1') throw new TypeError(`Неподдерживаемая версия ScenarioSpec: ${source.schema_version ?? 'не указана'}`);
  if (!/^calc_[0-9a-f]{16}$/.test(source.revision_id || '')) throw new TypeError('ScenarioSpec.revision_id имеет неверный формат');
  if (source.source !== 'calculation') throw new TypeError('ScenarioSpec.source должен быть calculation');
  if (!['warehouse', 'airport', 'hospital'].includes(source.template)) throw new TypeError(`Неподдерживаемый template: ${source.template}`);
  if (typeof source.seed !== 'string' || !source.seed.trim()) throw new TypeError('ScenarioSpec.seed обязателен');
  if (!Array.isArray(source.zones) || !source.zones.length) throw new TypeError('ScenarioSpec должен содержать хотя бы одну зону');
  if (!Array.isArray(source.fleet) || !Array.isArray(source.task_profiles)) throw new TypeError('ScenarioSpec.fleet и task_profiles должны быть массивами');
  rejectUnknown(source.presentation, PRESENTATION_FIELDS, 'ScenarioSpec.presentation'); rejectUnknown(source.facility, FACILITY_FIELDS, 'ScenarioSpec.facility'); rejectUnknown(source.economics, ECONOMICS_FIELDS, 'ScenarioSpec.economics');
  if (!Array.isArray(source.assumptions) || !Array.isArray(source.warnings)) throw new TypeError('ScenarioSpec.assumptions и warnings должны быть массивами');
  if (source.warnings.some(item => typeof item !== 'string')) throw new TypeError('ScenarioSpec.warnings должен содержать только строки');
  source.assumptions.forEach((item, index) => rejectUnknown(item, ASSUMPTION_FIELDS, `ScenarioSpec.assumptions[${index}]`));
}

function quantityV2(value, path, expectedUnit = null) {
  rejectUnknown(value, V2_QUANTITY_FIELDS, path);
  if (value.numeric_encoding !== 'DECIMAL_STRING' || typeof value.value !== 'string' || !/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value.value)) throw new TypeError(`${path} должен содержать canonical DECIMAL_STRING`);
  if (typeof value.unit !== 'string' || !value.unit || typeof value.quantity_kind !== 'string' || !value.quantity_kind) throw new TypeError(`${path} требует unit и quantity_kind`);
  if (expectedUnit && value.unit !== expectedUnit) throw new TypeError(`${path}.unit должен быть ${expectedUnit}`);
  const parsed = Number(value.value);
  if (!Number.isFinite(parsed)) throw new TypeError(`${path}.value выходит за числовой диапазон renderer`);
  return parsed;
}

function validateV2Root(source) {
  rejectUnknown(source, V2_ROOT_FIELDS, 'ScenarioSpec');
  if (source.schema_version !== 'scenario-spec-v2') throw new TypeError(`Неподдерживаемая версия ScenarioSpec: ${source.schema_version ?? 'не указана'}`);
  if (!/^calc_[0-9a-f]{16}$/.test(source.revision_id || '')) throw new TypeError('ScenarioSpec.revision_id имеет неверный формат');
  if (source.source !== 'capacity-analysis') throw new TypeError('ScenarioSpec v2 source должен быть capacity-analysis');
  if (!['warehouse', 'airport', 'hospital'].includes(source.template)) throw new TypeError(`Неподдерживаемый template: ${source.template}`);
  if (!/^scenario-[0-9a-f]{16}$/.test(source.seed || '')) throw new TypeError('ScenarioSpec v2 seed имеет неверный формат');
  rejectUnknown(source.analysis, V2_ANALYSIS_FIELDS, 'ScenarioSpec.analysis');
  rejectUnknown(source.versions, V2_VERSION_FIELDS, 'ScenarioSpec.versions');
  rejectUnknown(source.versions.calculation, V2_CALCULATION_VERSION_FIELDS, 'ScenarioSpec.versions.calculation');
  rejectUnknown(source.profile, V2_PROFILE_FIELDS, 'ScenarioSpec.profile');
  if (!V2_PROCESS[source.profile.calculation_profile]) throw new TypeError(`Неподдерживаемый calculation_profile: ${source.profile.calculation_profile}`);
  if (!Array.isArray(source.operating_windows) || !source.operating_windows.length || !Array.isArray(source.zones) || !source.zones.length || !Array.isArray(source.routes) || !Array.isArray(source.fleet) || !Array.isArray(source.tasks) || !Array.isArray(source.assumptions) || !Array.isArray(source.trace_node_refs) || !Array.isArray(source.warnings)) throw new TypeError('ScenarioSpec v2 содержит некорректные коллекции');
  source.assumptions.forEach((item, index) => rejectUnknown(item, V2_ASSUMPTION_FIELDS, `ScenarioSpec.assumptions[${index}]`));
  if (source.warnings.some(item => typeof item !== 'string') || source.trace_node_refs.some(item => typeof item !== 'string')) throw new TypeError('ScenarioSpec v2 warnings/trace_node_refs должны содержать строки');
}

function exchangeSecondsV2(exchange, path) {
  rejectUnknown(exchange, V2_EXCHANGE_FIELDS, path);
  if (exchange.mode === 'NOT_APPLICABLE') {
    if (exchange.total_time !== null || exchange.load_time !== null || exchange.unload_time !== null) throw new TypeError(`${path} NOT_APPLICABLE не содержит времена`);
    return 0;
  }
  if (exchange.mode === 'TOTAL') {
    if (!exchange.total_time || exchange.load_time !== null || exchange.unload_time !== null) throw new TypeError(`${path} TOTAL требует только total_time`);
    return quantityV2(exchange.total_time, `${path}.total_time`, 's');
  }
  if (exchange.mode === 'SPLIT') {
    if (exchange.total_time !== null || !exchange.load_time || !exchange.unload_time) throw new TypeError(`${path} SPLIT требует load_time и unload_time`);
    return quantityV2(exchange.load_time, `${path}.load_time`, 's') + quantityV2(exchange.unload_time, `${path}.unload_time`, 's');
  }
  throw new TypeError(`${path}.mode не поддерживается`);
}

function parseScenarioSpecV2(source) {
  validateV2Root(source);
  const windowMap = new Map();
  source.operating_windows.forEach((window, index) => {
    rejectUnknown(window, V2_WINDOW_FIELDS, `ScenarioSpec.operating_windows[${index}]`);
    if (windowMap.has(window.window_id)) throw new TypeError(`Повторяющийся window_id: ${window.window_id}`);
    quantityV2(window.start_time, `operating_windows[${index}].start_time`, 's');
    const duration = quantityV2(window.duration, `operating_windows[${index}].duration`, 'h');
    if (duration <= 0) throw new TypeError(`operating_windows[${index}].duration должен быть положительным`);
    windowMap.set(window.window_id, duration);
  });
  const zoneIds = new Set();
  source.zones.forEach((zone, index) => {
    rejectUnknown(zone, V2_ZONE_FIELDS, `ScenarioSpec.zones[${index}]`);
    if (zoneIds.has(zone.zone_id)) throw new TypeError(`Повторяющийся zone_id: ${zone.zone_id}`);
    if (!['PROVIDED', 'SYNTHETIC', 'UNKNOWN'].includes(zone.geometry_source)) throw new TypeError(`Неизвестный geometry_source зоны ${zone.zone_id}`);
    if (zone.geometry_source === 'PROVIDED' && !zone.geometry_ref) throw new TypeError(`Provided geometry зоны ${zone.zone_id} требует geometry_ref`);
    if (zone.geometry_source === 'SYNTHETIC' && !zone.assumption_ref) throw new TypeError(`Synthetic geometry зоны ${zone.zone_id} требует assumption_ref`);
    zoneIds.add(zone.zone_id);
  });
  const routeMap = new Map();
  source.routes.forEach((route, index) => {
    rejectUnknown(route, V2_ROUTE_FIELDS, `ScenarioSpec.routes[${index}]`);
    if (routeMap.has(route.route_id)) throw new TypeError(`Повторяющийся route_id: ${route.route_id}`);
    if (!['PROVIDED', 'SYNTHETIC', 'NOT_APPLICABLE'].includes(route.geometry_source)) throw new TypeError(`Неизвестный geometry_source маршрута ${route.route_id}`);
    if (route.one_way_distance) quantityV2(route.one_way_distance, `routes[${index}].one_way_distance`, 'm');
    routeMap.set(route.route_id, route);
  });
  source.fleet.forEach((fleet, index) => {
    rejectUnknown(fleet, V2_FLEET_FIELDS, `ScenarioSpec.fleet[${index}]`);
    ['nominal_capacity', 'effective_capacity', 'coverage'].forEach(field => quantityV2(fleet[field], `fleet[${index}].${field}`));
    if (fleet.raw_load_ratio) quantityV2(fleet.raw_load_ratio, `fleet[${index}].raw_load_ratio`);
    if (fleet.utilization) quantityV2(fleet.utilization, `fleet[${index}].utilization`);
  });
  source.tasks.forEach((task, index) => {
    rejectUnknown(task, V2_TASK_FIELDS, `ScenarioSpec.tasks[${index}]`);
    quantityV2(task.demand, `tasks[${index}].demand`);
    rejectUnknown(task.batch, V2_BATCH_FIELDS, `tasks[${index}].batch`);
    quantityV2(task.batch.units_per_cycle, `tasks[${index}].batch.units_per_cycle`);
    exchangeSecondsV2(task.exchange, `tasks[${index}].exchange`);
    if (!zoneIds.has(task.zone_id) || task.operating_window_refs.some(ref => !windowMap.has(ref)) || (task.route_ref !== null && !routeMap.has(task.route_ref))) throw new TypeError(`ScenarioSpec task ${task.task_id} содержит несогласованные ссылки`);
  });
  const profile = V2_PROCESS[source.profile.calculation_profile];
  const zones = source.zones.map(zone => {
    const task = source.tasks.find(item => item.zone_id === zone.zone_id && item.process_id === source.profile.process_id);
    const fleet = source.fleet.find(item => item.zone_id === zone.zone_id && item.process_id === source.profile.process_id);
    const normalizedZone = deepFreeze({ id: zone.zone_id, name: zone.label, process_type: profile.processType, polygon: null, geometry_source: zone.geometry_source, geometry_ref: zone.geometry_ref });
    if (!task || !fleet || fleet.selected_fleet < 1) return Object.freeze({ zone: normalizedZone, supported: false, reason: 'NO_RENDERABLE_FLEET_OR_TASK' });
    const demandPerDay = quantityV2(task.demand, `task ${task.task_id}.demand`);
    const unitsPerTrip = quantityV2(task.batch.units_per_cycle, `task ${task.task_id}.batch.units_per_cycle`);
    const operatingHoursPerDay = task.operating_window_refs.reduce((sum, ref) => sum + windowMap.get(ref), 0);
    if (demandPerDay <= 0 || unitsPerTrip <= 0 || operatingHoursPerDay <= 0) throw new TypeError(`Task ${task.task_id} требует положительные demand, batch и operating window`);
    const route = task.route_ref === null ? null : routeMap.get(task.route_ref);
    const scenario = Object.freeze({
      revisionId: source.revision_id, scenarioSchemaVersion: source.schema_version, scenarioSeed: source.seed,
      zoneId: zone.zone_id, zoneName: zone.label, processType: profile.processType,
      equipmentModelId: fleet.model_id, visualProfile: `conceptual-${profile.processType}`, internalProfile: profile.internalProfile,
      quantity: positiveInteger(fleet.selected_fleet, `fleet ${fleet.fleet_id}.selected_fleet`, 100),
      maxSpeedMS: profile.speed, payloadKg: 0, visualKinematicsSource: 'CONCEPTUAL_RENDERER_DEFAULT_V1',
      taskKind: profile.taskKind, demandPerDay, demandUnit: task.demand.unit, unitsPerTrip,
      exchangeTimeS: exchangeSecondsV2(task.exchange, `task ${task.task_id}.exchange`),
      operatingHoursPerDay, operatingWindowRefs: Object.freeze([...task.operating_window_refs]),
      taskIntervalS: operatingHoursPerDay * 3600 * unitsPerTrip / demandPerDay,
      geometryMode: zone.geometry_source, polygonProvided: zone.geometry_source === 'PROVIDED',
      analyticalRoute: route ? deepFreeze(clone(route)) : null,
      visualizationOnly: source.profile.capacity_status !== 'COMPLETE', financeStatus: source.finance === null ? 'NOT_PROVIDED' : 'IMMUTABLE_REFERENCE'
    });
    return Object.freeze({ zone: normalizedZone, supported: true, scenario });
  });
  return Object.freeze({ spec: deepFreeze(clone(source)), revisionId: source.revision_id, template: source.template, zones });
}

function parseZone(source, zone, index) {
  rejectUnknown(zone, ZONE_FIELDS, `ScenarioSpec.zones[${index}]`);
  if (typeof zone.id !== 'string' || !zone.id || typeof zone.name !== 'string' || !zone.name) throw new TypeError(`ScenarioSpec.zones[${index}] требует id и name`);
  if (!PROCESS_TASK_KINDS[zone.process_type]) throw new TypeError(`Неподдерживаемый process_type: ${zone.process_type}`);
  if (!['RECOMMENDED', 'NO_ELIGIBLE_EQUIPMENT', 'NO_ACCEPTABLE_ECONOMICS'].includes(zone.status)) throw new TypeError(`Неизвестный статус зоны ${zone.id}`);
  if (zone.polygon !== null && (!Array.isArray(zone.polygon) || zone.polygon.length < 3 || zone.polygon.some(point => !Array.isArray(point) || point.length !== 2 || point.some(value => !Number.isFinite(value))))) throw new TypeError(`zones[${index}].polygon должен содержать минимум три точки [x, z]`);
  const fleets = source.fleet.filter(item => item.zone_id === zone.id); const tasks = source.task_profiles.filter(item => item.zone_id === zone.id);
  if (zone.status === 'NO_ELIGIBLE_EQUIPMENT') {
    if (fleets.length || tasks.length) throw new TypeError(`Зона ${zone.id} без допустимого оборудования не должна содержать fleet/task_profile`);
    return Object.freeze({ zone: deepFreeze(clone(zone)), supported: false, reason: zone.status });
  }
  if (zone.status === 'NO_ACCEPTABLE_ECONOMICS' && !fleets.length && !tasks.length) {
    return Object.freeze({ zone: deepFreeze(clone(zone)), supported: false, reason: zone.status });
  }
  if (fleets.length !== 1 || tasks.length !== 1) throw new TypeError(`Зона ${zone.id} требует ровно одну согласованную запись fleet и task_profile`);
  const fleet = fleets[0]; const task = tasks[0]; const fleetIndex = source.fleet.indexOf(fleet); const taskIndex = source.task_profiles.indexOf(task);
  rejectUnknown(fleet, FLEET_FIELDS, `ScenarioSpec.fleet[${fleetIndex}]`); rejectUnknown(task, TASK_FIELDS, `ScenarioSpec.task_profiles[${taskIndex}]`);
  const internalProfile = VISUAL_PROFILE_MAP[fleet.visual_profile]; const supportedMatrix = zone.process_type !== 'delivery' || source.template === 'hospital';
  if (!internalProfile || !PROCESS_TASK_KINDS[zone.process_type].has(task.kind) || !supportedMatrix) {
    const detail = !internalProfile ? `visual_profile=${fleet.visual_profile}` : !supportedMatrix ? 'delivery вне hospital' : `task kind=${task.kind}`;
    return Object.freeze({ zone: deepFreeze(clone(zone)), supported: false, reason: `UNSUPPORTED_3D: ${detail}` });
  }
  const demandPerDay = positiveNumber(task.demand_per_day, `task_profiles[${taskIndex}].demand_per_day`); const zoneDemandPerDay = positiveNumber(zone.demand_per_day, `zones[${index}].demand_per_day`);
  if (demandPerDay !== zoneDemandPerDay) throw new TypeError(`Спрос task_profile должен совпадать со спросом зоны ${zone.id}`);
  const unitsPerTrip = positiveInteger(task.units_per_trip, `task_profiles[${taskIndex}].units_per_trip`, 100000);
  const scenario = Object.freeze({
    revisionId: source.revision_id, zoneId: zone.id, zoneName: zone.name, processType: zone.process_type,
    equipmentModelId: fleet.equipment_model_id, visualProfile: fleet.visual_profile, internalProfile,
    quantity: positiveInteger(fleet.quantity, `fleet[${fleetIndex}].quantity`, 100),
    maxSpeedMS: positiveNumber(fleet.max_speed_m_s, `fleet[${fleetIndex}].max_speed_m_s`, zone.process_type === 'palletizing'),
    payloadKg: positiveNumber(fleet.payload_kg, `fleet[${fleetIndex}].payload_kg`, true),
    taskKind: task.kind, demandPerDay, unitsPerTrip,
    exchangeTimeS: positiveNumber(task.exchange_time_s, `task_profiles[${taskIndex}].exchange_time_s`, true),
    taskIntervalS: 86400 * unitsPerTrip / demandPerDay,
    geometryMode: 'REPRESENTATIVE', polygonProvided: Boolean(zone.polygon),
    visualizationOnly: zone.status === 'NO_ACCEPTABLE_ECONOMICS'
  });
  return Object.freeze({ zone: deepFreeze(clone(zone)), supported: true, scenario });
}

export function parseScenarioSpec(source) {
  if (source?.schema_version === 'scenario-spec-v2') return parseScenarioSpecV2(source);
  if (source?.schema_version !== 'scenario-spec-v1') throw new TypeError(`Неподдерживаемая версия ScenarioSpec: ${source?.schema_version ?? 'не указана'}`);
  validateRoot(source); const ids = source.zones.map(zone => zone.id);
  if (new Set(ids).size !== ids.length) throw new TypeError('ScenarioSpec zone.id должны быть уникальны');
  const known = new Set(ids); const dangling = [...source.fleet, ...source.task_profiles].filter(item => !known.has(item.zone_id)).map(item => item.zone_id);
  if (dangling.length) throw new TypeError(`ScenarioSpec содержит неизвестные zone_id: ${[...new Set(dangling)].join(', ')}`);
  const zones = source.zones.map((zone, index) => parseZone(source, zone, index));
  return Object.freeze({ spec: deepFreeze(clone(source)), revisionId: source.revision_id, template: source.template, zones });
}

export function parseWarehouseScenarioSpec(source) {
  const parsed = parseScenarioSpec(source);
  if (parsed.zones.length === 1 && parsed.zones[0].zone.process_type === 'transport' && parsed.zones[0].reason?.includes('task kind')) throw new TypeError(parsed.zones[0].reason);
  if (parsed.template !== 'warehouse' || parsed.zones.length !== 1 || parsed.zones[0].zone.process_type !== 'transport' || !parsed.zones[0].supported) throw new TypeError('Этап B требует ровно одну рекомендованную warehouse transport-зону');
  return Object.freeze({ spec: parsed.spec, ...parsed.zones[0].scenario });
}
