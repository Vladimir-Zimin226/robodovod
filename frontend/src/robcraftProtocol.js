export const ROBCRAFT_MESSAGE_VERSION = 'robcraft-message-v1';
const SCENARIO_SPEC_VERSIONS = new Set(['scenario-spec-v1', 'scenario-spec-v2']);

const CHILD_TYPES = new Set(['ROBCRAFT_READY', 'SCENARIO_LOADED', 'CAMERA_MODE_CHANGED', 'EDITOR_MODE_CHANGED', 'SCENE_PATCH_CHANGED', 'ROBCRAFT_REPORT', 'ROBCRAFT_ERROR']);
const ROOT_FIELDS = new Set(['schema_version', 'type', 'revision_id', 'request_id', 'payload']);

function plainObject(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${path} должен быть объектом`);
  }
}

function exact(value, fields, path) {
  plainObject(value, path);
  const unknown = Object.keys(value).filter((key) => !fields.has(key));
  if (unknown.length) throw new TypeError(`${path}: неизвестные поля: ${unknown.join(', ')}`);
}

function decimalString(value, path, nullable = false) {
  if (nullable && value === null) return;
  if (typeof value !== 'string' || !/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value)) throw new TypeError(`${path} должен быть canonical decimal string`);
}

function rendererReport(value) {
  exact(value, new Set(['schema_version', 'status', 'bindings', 'versions', 'measurement_basis', 'geometry', 'observed', 'utilization', 'energy', 'model_status', 'limitations']), 'ROBCRAFT_REPORT.payload');
  if (value.schema_version !== 'robcraft-renderer-report-v1' || value.status !== 'LOCAL_VISUAL_OBSERVATION_ONLY') throw new TypeError('Неподдерживаемый renderer report');
  exact(value.bindings, new Set(['scenario_revision_id', 'scenario_spec_version', 'scenario_seed', 'authoritative_report_id', 'authoritative_report_digest', 'scheduler_seed']), 'ROBCRAFT_REPORT.bindings');
  if (!/^calc_[0-9a-f]{16}$/.test(value.bindings.scenario_revision_id || '') || !SCENARIO_SPEC_VERSIONS.has(value.bindings.scenario_spec_version)) throw new TypeError('Renderer report содержит неверные bindings');
  if (typeof value.bindings.scenario_seed !== 'string' || !value.bindings.scenario_seed) throw new TypeError('Renderer report scenario seed обязателен');
  if (value.bindings.authoritative_report_digest !== null && !/^sha256:[0-9a-f]{64}$/.test(value.bindings.authoritative_report_digest)) throw new TypeError('Renderer report digest имеет неверный формат');
  if ((value.bindings.authoritative_report_id === null) !== (value.bindings.authoritative_report_digest === null) || (value.bindings.scheduler_seed === null) !== (value.bindings.authoritative_report_digest === null)) throw new TypeError('Renderer report C23 bindings должны быть полными или отсутствовать');
  if (value.bindings.authoritative_report_id !== null && (typeof value.bindings.authoritative_report_id !== 'string' || !value.bindings.authoritative_report_id)) throw new TypeError('Renderer report ID имеет неверный формат');
  if (value.bindings.scheduler_seed !== null && !Number.isInteger(value.bindings.scheduler_seed)) throw new TypeError('Renderer report scheduler seed имеет неверный формат');
  exact(value.versions, new Set(['renderer_engine_version', 'event_profile_version', 'report_version']), 'ROBCRAFT_REPORT.versions');
  exact(value.measurement_basis, new Set(['kind', 'elapsed_seconds', 'operating_hours_per_day', 'operating_window_refs', 'warmup_days', 'measurement_days']), 'ROBCRAFT_REPORT.measurement_basis');
  if (value.measurement_basis.kind !== 'LIVE_RENDERER_WINDOW' || !Array.isArray(value.measurement_basis.operating_window_refs)) throw new TypeError('Renderer report measurement basis не поддерживается');
  decimalString(value.measurement_basis.elapsed_seconds, 'elapsed_seconds'); decimalString(value.measurement_basis.operating_hours_per_day, 'operating_hours_per_day');
  exact(value.geometry, new Set(['source', 'status', 'base_revision_id', 'economics_status', 'analytical_route_ref', 'analytical_distance_value', 'analytical_distance_unit']), 'ROBCRAFT_REPORT.geometry');
  if (!['PROVIDED', 'SYNTHETIC', 'UNKNOWN', 'REPRESENTATIVE'].includes(value.geometry.source) || value.geometry.base_revision_id !== value.bindings.scenario_revision_id || value.geometry.economics_status !== 'UNCHANGED' || !['BASE', 'MODIFIED'].includes(value.geometry.status)) throw new TypeError('Renderer report geometry status некорректен');
  if ((value.geometry.analytical_distance_value === null) !== (value.geometry.analytical_distance_unit === null)) throw new TypeError('Renderer report analytical distance должен содержать value и unit вместе');
  decimalString(value.geometry.analytical_distance_value, 'geometry.analytical_distance_value', true);
  exact(value.observed, new Set(['completed_units', 'throughput_units_per_hour', 'throughput_unit', 'queued_jobs', 'average_queue_seconds']), 'ROBCRAFT_REPORT.observed');
  ['completed_units', 'throughput_units_per_hour', 'average_queue_seconds'].forEach(field => decimalString(value.observed[field], `observed.${field}`));
  if (!Number.isInteger(value.observed.queued_jobs) || value.observed.queued_jobs < 0) throw new TypeError('observed.queued_jobs должен быть неотрицательным integer');
  exact(value.utilization, new Set(['moving_percent', 'moving_basis', 'productive_percent', 'productive_status']), 'ROBCRAFT_REPORT.utilization');
  decimalString(value.utilization.moving_percent, 'utilization.moving_percent'); decimalString(value.utilization.productive_percent, 'utilization.productive_percent', true);
  if (value.utilization.productive_status !== 'NOT_EVALUATED_LOCAL_TIME_STEP') throw new TypeError('Renderer report не должен выдавать moving utilization за productive');
  exact(value.energy, new Set(['value', 'unit', 'economics_status']), 'ROBCRAFT_REPORT.energy'); decimalString(value.energy.value, 'energy.value');
  if (value.energy.unit !== 'ARBITRARY_RENDERER_UNIT' || value.energy.economics_status !== 'NOT_COMPARABLE_TO_RUB_OR_KWH') throw new TypeError('Renderer energy не имеет допустимой маркировки');
  exact(value.model_status, new Set(['sla', 'failures', 'charging', 'engineering_claim']), 'ROBCRAFT_REPORT.model_status');
  if (value.model_status.sla !== 'NOT_EVALUATED_USE_C23_REPORT' || value.model_status.engineering_claim !== 'CONCEPTUAL_VISUALIZATION_NOT_CERTIFICATION') throw new TypeError('Renderer report содержит недопустимое SLA/engineering утверждение');
  if (!Array.isArray(value.limitations) || value.limitations.some(item => typeof item !== 'string')) throw new TypeError('Renderer report limitations некорректны');
}

export function parseRobCraftMessage(value) {
  exact(value, ROOT_FIELDS, 'RobCraftMessage');
  if (value.schema_version !== ROBCRAFT_MESSAGE_VERSION) throw new TypeError('Неподдерживаемая версия сообщений RobCraft');
  if (!CHILD_TYPES.has(value.type)) throw new TypeError(`Неподдерживаемое сообщение RobCraft: ${value.type}`);
  plainObject(value.payload, 'RobCraftMessage.payload');

  if (value.type === 'ROBCRAFT_READY') {
    if (value.revision_id !== null || value.request_id !== null) throw new TypeError('ROBCRAFT_READY не должен содержать ревизию');
    exact(value.payload, new Set(['capabilities']), 'ROBCRAFT_READY.payload');
    if (!Array.isArray(value.payload.capabilities) || value.payload.capabilities.some((item) => typeof item !== 'string')) throw new TypeError('capabilities должен быть массивом строк');
  } else {
    const bootstrapError = value.type === 'ROBCRAFT_ERROR' && value.revision_id === null && value.request_id === null;
    if (!bootstrapError && !/^calc_[0-9a-f]{16}$/.test(value.revision_id || '')) throw new TypeError('revision_id имеет неверный формат');
    if (!bootstrapError && (typeof value.request_id !== 'string' || !value.request_id.startsWith('request_'))) throw new TypeError('request_id имеет неверный формат');
    if (value.type === 'SCENARIO_LOADED') {
      exact(value.payload, new Set(['status']), 'SCENARIO_LOADED.payload');
      if (!['PREPARED', 'APPLIED'].includes(value.payload.status)) throw new TypeError('Неизвестный статус загрузки сцены');
    } else if (value.type === 'CAMERA_MODE_CHANGED') {
      exact(value.payload, new Set(['mode', 'reason', 'pointer_locked']), 'CAMERA_MODE_CHANGED.payload');
      if (!['AUTOPILOT', 'MANUAL_FIRST_PERSON'].includes(value.payload.mode)) throw new TypeError('Неизвестный режим камеры');
      if (typeof value.payload.reason !== 'string' || typeof value.payload.pointer_locked !== 'boolean') throw new TypeError('Некорректное состояние камеры');
    } else if (value.type === 'EDITOR_MODE_CHANGED') {
      exact(value.payload, new Set(['enabled', 'scene_status', 'simulation_paused']), 'EDITOR_MODE_CHANGED.payload');
      if (typeof value.payload.enabled !== 'boolean' || typeof value.payload.simulation_paused !== 'boolean' || !['CLEAN', 'MODIFIED'].includes(value.payload.scene_status)) throw new TypeError('Некорректное состояние редактора');
    } else if (value.type === 'SCENE_PATCH_CHANGED') {
      exact(value.payload, new Set(['format', 'base_revision_id', 'visual_fingerprint', 'zone_id', 'status', 'economics_status', 'summary']), 'SCENE_PATCH_CHANGED.payload');
      if (value.payload.format !== 'robcraft-scene-patch-v1' || value.payload.base_revision_id !== value.revision_id || !/^visual_[0-9a-f]{8}$/.test(value.payload.visual_fingerprint || '') || typeof value.payload.zone_id !== 'string' || !value.payload.zone_id || !['CLEAN', 'MODIFIED'].includes(value.payload.status) || value.payload.economics_status !== 'UNCHANGED') throw new TypeError('Некорректное состояние ScenePatch');
      exact(value.payload.summary, new Set(['objects', 'created', 'deleted', 'robots']), 'SCENE_PATCH_CHANGED.payload.summary');
      if (Object.values(value.payload.summary).some(count => !Number.isInteger(count) || count < 0)) throw new TypeError('Некорректная сводка ScenePatch');
    } else if (value.type === 'ROBCRAFT_REPORT') {
      rendererReport(value.payload);
      if (value.payload.bindings.scenario_revision_id !== value.revision_id) throw new TypeError('Renderer report не связан с revision envelope');
    } else {
      exact(value.payload, new Set(['code', 'message']), 'ROBCRAFT_ERROR.payload');
      if (typeof value.payload.code !== 'string' || typeof value.payload.message !== 'string') throw new TypeError('Некорректная ошибка RobCraft');
    }
  }
  return value;
}

export function negotiateScenarioSpec(scenarioSpec, capabilities) {
  plainObject(scenarioSpec, 'ScenarioSpec');
  if (!SCENARIO_SPEC_VERSIONS.has(scenarioSpec.schema_version)) {
    throw new TypeError(`Неподдерживаемая версия ScenarioSpec: ${scenarioSpec.schema_version ?? 'не указана'}`);
  }
  if (!Array.isArray(capabilities) || capabilities.some((item) => typeof item !== 'string')) {
    throw new TypeError('RobCraft capabilities должен быть массивом строк');
  }
  if (!capabilities.includes(scenarioSpec.schema_version)) {
    throw new TypeError(`RobCraft не объявил поддержку ${scenarioSpec.schema_version}`);
  }
  return scenarioSpec;
}

export function parentMessage(type, revisionId, requestId, payload = {}) {
  return {
    schema_version: ROBCRAFT_MESSAGE_VERSION,
    type,
    revision_id: revisionId,
    request_id: requestId,
    payload,
  };
}
