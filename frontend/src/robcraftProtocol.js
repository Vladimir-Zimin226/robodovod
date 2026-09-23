export const ROBCRAFT_MESSAGE_VERSION = 'robcraft-message-v1';
const SCENARIO_SPEC_VERSIONS = new Set(['scenario-spec-v1', 'scenario-spec-v2']);

const CHILD_TYPES = new Set(['ROBCRAFT_READY', 'SCENARIO_LOADED', 'CAMERA_MODE_CHANGED', 'EDITOR_MODE_CHANGED', 'SCENE_PATCH_CHANGED', 'ROBCRAFT_ERROR']);
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
