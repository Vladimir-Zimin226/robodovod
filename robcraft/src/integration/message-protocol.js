export const MESSAGE_SCHEMA_VERSION = 'robcraft-message-v1';

const INBOUND_TYPES = new Set(['LOAD_SCENARIO', 'APPLY_REVISION', 'SET_CAMERA_MODE', 'SET_EDITOR_MODE']);
const CAMERA_MODES = new Set(['AUTOPILOT', 'MANUAL_FIRST_PERSON']);
const ENVELOPE_FIELDS = new Set([
  'schema_version', 'type', 'revision_id', 'request_id', 'payload'
]);

function assertPlainObject(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${path} должен быть объектом`);
  }
}

function assertExactFields(value, allowed, path) {
  assertPlainObject(value, path);
  const unknown = Object.keys(value).filter(key => !allowed.has(key));
  if (unknown.length) throw new TypeError(`${path}: неизвестные поля: ${unknown.join(', ')}`);
}

export function parseParentMessage(value) {
  assertExactFields(value, ENVELOPE_FIELDS, 'RobCraftMessage');
  if (value.schema_version !== MESSAGE_SCHEMA_VERSION) {
    throw new TypeError(`Неподдерживаемая версия сообщений: ${value.schema_version ?? 'не указана'}`);
  }
  if (!INBOUND_TYPES.has(value.type)) throw new TypeError(`Неподдерживаемый тип сообщения: ${value.type}`);
  if (!/^calc_[0-9a-f]{16}$/.test(value.revision_id || '')) {
    throw new TypeError('revision_id имеет неверный формат');
  }
  if (typeof value.request_id !== 'string' || !/^request_[a-zA-Z0-9_-]{1,80}$/.test(value.request_id)) {
    throw new TypeError('request_id имеет неверный формат');
  }
  assertPlainObject(value.payload, 'RobCraftMessage.payload');
  if (value.type === 'LOAD_SCENARIO') {
    assertExactFields(value.payload, new Set(['scenario_spec']), 'LOAD_SCENARIO.payload');
    assertPlainObject(value.payload.scenario_spec, 'LOAD_SCENARIO.payload.scenario_spec');
    if (value.payload.scenario_spec.revision_id !== value.revision_id) {
      throw new TypeError('revision_id сообщения и ScenarioSpec не совпадают');
    }
  } else if (value.type === 'APPLY_REVISION') {
    assertExactFields(value.payload, new Set(), 'APPLY_REVISION.payload');
  } else if (value.type === 'SET_CAMERA_MODE') {
    assertExactFields(value.payload, new Set(['mode']), 'SET_CAMERA_MODE.payload');
    if (!CAMERA_MODES.has(value.payload.mode)) throw new TypeError('Неподдерживаемый режим камеры');
  } else {
    assertExactFields(value.payload, new Set(['enabled']), 'SET_EDITOR_MODE.payload');
    if (typeof value.payload.enabled !== 'boolean') throw new TypeError('SET_EDITOR_MODE.enabled должен быть boolean');
  }
  return value;
}

export function childMessage(type, revisionId, requestId, payload = {}) {
  return {
    schema_version: MESSAGE_SCHEMA_VERSION,
    type,
    revision_id: revisionId,
    request_id: requestId,
    payload
  };
}

export function installParentBridge(windowObject, { prepare, apply, setCameraMode, getCameraState, setEditorMode, getEditorState, getScenePatchState }) {
  if (windowObject.parent === windowObject) return { dispose() {}, cameraModeChanged() {}, editorModeChanged() {}, scenePatchChanged() {} };
  const origin = windowObject.location.origin;
  let prepared = null;
  let applied = null;

  const send = message => windowObject.parent.postMessage(message, origin);
  const fail = (error, source = {}) => send(childMessage(
    'ROBCRAFT_ERROR',
    source.revision_id ?? null,
    source.request_id ?? null,
    {
      code: source.type === 'SET_CAMERA_MODE' ? 'CAMERA_CONTROL_REJECTED' : source.type === 'SET_EDITOR_MODE' ? 'EDITOR_CONTROL_REJECTED' : 'SCENARIO_REJECTED',
      message: error instanceof Error ? error.message : String(error)
    }
  ));
  const cameraModeChanged = (mode, reason = 'STATE_CHANGED', pointerLocked = false) => {
    if (!applied) return;
    send(childMessage('CAMERA_MODE_CHANGED', applied.revisionId, applied.requestId, {
      mode, reason, pointer_locked: Boolean(pointerLocked)
    }));
  };
  const editorModeChanged = (state = {}) => {
    if (!applied) return;
    send(childMessage('EDITOR_MODE_CHANGED', applied.revisionId, applied.requestId, {
      enabled: Boolean(state.enabled),
      scene_status: state.sceneStatus === 'MODIFIED' ? 'MODIFIED' : 'CLEAN',
      simulation_paused: Boolean(state.simulationPaused)
    }));
  };
  const scenePatchChanged = (state = {}) => {
    if (!applied) return;
    send(childMessage('SCENE_PATCH_CHANGED', applied.revisionId, applied.requestId, {
      format: 'robcraft-scene-patch-v1',
      base_revision_id: state.baseRevisionId,
      visual_fingerprint: state.visualFingerprint,
      zone_id: state.zoneId,
      status: state.status === 'MODIFIED' ? 'MODIFIED' : 'CLEAN',
      economics_status: 'UNCHANGED',
      summary: state.summary || { objects: 0, created: 0, deleted: 0, robots: 0 }
    }));
  };

  const listener = async event => {
    if (event.origin !== origin || event.source !== windowObject.parent) return;
    let message;
    try {
      message = parseParentMessage(event.data);
      if (message.type === 'LOAD_SCENARIO') {
        const candidate = await prepare(message.payload.scenario_spec);
        prepared = { revisionId: message.revision_id, requestId: message.request_id, candidate };
        send(childMessage('SCENARIO_LOADED', message.revision_id, message.request_id, { status: 'PREPARED' }));
        return;
      }
      if (message.type === 'APPLY_REVISION') {
        if (!prepared || prepared.revisionId !== message.revision_id || prepared.requestId !== message.request_id) {
          throw new TypeError('Ревизия не подготовлена или уже устарела');
        }
        await apply(prepared.candidate);
        applied = prepared;
        prepared = null;
        send(childMessage('SCENARIO_LOADED', applied.revisionId, applied.requestId, { status: 'APPLIED' }));
        const state = getCameraState?.();
        if (state) cameraModeChanged(state.mode, 'REVISION_APPLIED', state.pointerLocked);
        const editorState = getEditorState?.();
        if (editorState) editorModeChanged(editorState);
        const patchState = getScenePatchState?.();
        if (patchState) scenePatchChanged(patchState);
        return;
      }
      if (!applied || applied.revisionId !== message.revision_id || applied.requestId !== message.request_id) {
        throw new TypeError('Управление запрошено для неактивной ревизии');
      }
      if (message.type === 'SET_CAMERA_MODE') {
        const state = await setCameraMode(message.payload.mode);
        cameraModeChanged(state.mode, state.reason || 'PARENT_REQUEST', state.pointerLocked);
      } else {
        const state = await setEditorMode(message.payload.enabled);
        editorModeChanged(state);
      }
    } catch (error) {
      fail(error, message || (event.data && typeof event.data === 'object' ? event.data : {}));
    }
  };

  windowObject.addEventListener('message', listener);
  send(childMessage('ROBCRAFT_READY', null, null, { capabilities: ['scenario-spec-v1', 'two-phase-apply', 'scene-patch-v1', 'embedded-editor', 'multi-zone-representative-v1', 'transport', 'clinical-delivery', 'cleaning-coverage', 'stationary-palletizing'] }));
  return {
    dispose: () => windowObject.removeEventListener('message', listener),
    cameraModeChanged,
    editorModeChanged,
    scenePatchChanged
  };
}
