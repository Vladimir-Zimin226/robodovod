const ROOT_FIELDS = new Set(['schema_version', 'revision_id', 'source', 'template', 'seed', 'presentation', 'facility', 'zones', 'fleet', 'task_profiles', 'economics', 'assumptions', 'warnings']);
const ZONE_FIELDS = new Set(['id', 'name', 'process_type', 'cargo_type', 'status', 'demand_per_day', 'avg_distance_m', 'aisle_width_m', 'polygon']);
const FLEET_FIELDS = new Set(['zone_id', 'equipment_model_id', 'visual_profile', 'quantity', 'max_speed_m_s', 'payload_kg']);
const TASK_FIELDS = new Set(['zone_id', 'kind', 'demand_per_day', 'units_per_trip', 'exchange_time_s']);
const PRESENTATION_FIELDS = new Set(['autoplay', 'default_camera_mode', 'manual_control_available', 'editor_available']);
const FACILITY_FIELDS = new Set(['area_m2', 'width_m', 'depth_m', 'geometry_status', 'occupancy_percent']);
const ECONOMICS_FIELDS = new Set(['scenario', 'horizon_years', 'capex_rub', 'annual_opex_rub', 'annual_savings_rub', 'payback_years', 'npv_rub', 'tco_rub', 'fte_released', 'confidence', 'status']);
const ASSUMPTION_FIELDS = new Set(['code', 'message']);
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
