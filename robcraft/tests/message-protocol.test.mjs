import test from 'node:test';
import assert from 'node:assert/strict';

import { installParentBridge, parseParentMessage } from '../src/integration/message-protocol.js';

const revision = 'calc_0123456789abcdef';
const requestId = 'request_stage_d';

function envelope(type, payload = {}) {
  return { schema_version: 'robcraft-message-v1', type, revision_id: revision, request_id: requestId, payload };
}

test('validates the message envelope and revision consistency', () => {
  const scenario = { revision_id: revision };
  assert.equal(parseParentMessage(envelope('LOAD_SCENARIO', { scenario_spec: scenario })).type, 'LOAD_SCENARIO');
  assert.throws(() => parseParentMessage({ ...envelope('APPLY_REVISION'), extra: true }), /неизвестные поля/);
  assert.throws(() => parseParentMessage(envelope('LOAD_SCENARIO', {
    scenario_spec: { revision_id: 'calc_ffffffffffffffff' },
  })), /не совпадают/);
  assert.throws(() => parseParentMessage(envelope('SET_CAMERA_MODE', { mode: 'EDITOR' })), /режим камеры/);
  assert.equal(parseParentMessage(envelope('SET_EDITOR_MODE', { enabled: true })).payload.enabled, true);
  assert.throws(() => parseParentMessage(envelope('SET_EDITOR_MODE', { enabled: 'yes' })), /boolean/);
});

test('editor control and ScenePatch status are revision-bound', async () => {
  const sent = [];
  const listeners = new Map();
  const parent = { postMessage: message => sent.push(message) };
  const fakeWindow = {
    parent,
    location: { origin: 'http://same-origin.test' },
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: () => {},
  };
  const bridge = installParentBridge(fakeWindow, {
    prepare: async () => ({}), apply: async () => {},
    setEditorMode: async enabled => ({ enabled, sceneStatus: 'MODIFIED', simulationPaused: enabled }),
    getEditorState: () => ({ enabled: false, sceneStatus: 'CLEAN', simulationPaused: false }),
    getScenePatchState: () => ({ baseRevisionId: revision, visualFingerprint: 'visual_1234abcd', zoneId: 'receiving', status: 'CLEAN', summary: { objects: 0, created: 0, deleted: 0, robots: 0 } }),
  });
  const scenario = { revision_id: revision };
  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('LOAD_SCENARIO', { scenario_spec: scenario }) });
  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('APPLY_REVISION') });
  assert.ok(sent.some(message => message.type === 'SCENE_PATCH_CHANGED' && message.payload.status === 'CLEAN'));
  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('SET_EDITOR_MODE', { enabled: true }) });
  assert.deepEqual(sent.at(-1).payload, { enabled: true, scene_status: 'MODIFIED', simulation_paused: true });
  bridge.scenePatchChanged({ baseRevisionId: revision, visualFingerprint: 'visual_1234abcd', zoneId: 'receiving', status: 'MODIFIED', summary: { objects: 1, created: 0, deleted: 0, robots: 0 } });
  assert.equal(sent.at(-1).payload.economics_status, 'UNCHANGED');
});

test('ignores foreign senders and applies only a prepared matching revision', async () => {
  const sent = [];
  const listeners = new Map();
  const parent = { postMessage: (message, origin) => sent.push({ message, origin }) };
  const fakeWindow = {
    parent,
    location: { origin: 'http://same-origin.test' },
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: (name) => listeners.delete(name),
  };
  let applied = null;
  const bridge = installParentBridge(fakeWindow, {
    prepare: async (spec) => ({ spec }),
    apply: async (candidate) => { applied = candidate; },
    setCameraMode: async (mode) => ({ mode, reason: 'TEST', pointerLocked: mode === 'MANUAL_FIRST_PERSON' }),
    getCameraState: () => ({ mode: 'AUTOPILOT', pointerLocked: false }),
  });

  assert.equal(sent[0].message.type, 'ROBCRAFT_READY');
  await listeners.get('message')({ origin: 'http://foreign.test', source: parent, data: envelope('APPLY_REVISION') });
  assert.equal(sent.length, 1);

  const scenario = { revision_id: revision };
  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('LOAD_SCENARIO', { scenario_spec: scenario }) });
  assert.equal(sent.at(-1).message.payload.status, 'PREPARED');
  assert.equal(applied, null);

  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('APPLY_REVISION') });
  assert.equal(sent.at(-2).message.payload.status, 'APPLIED');
  assert.equal(sent.at(-1).message.type, 'CAMERA_MODE_CHANGED');
  assert.deepEqual(applied.spec, scenario);
  bridge.dispose();
});

test('rejects apply for a stale request', async () => {
  const sent = [];
  const listeners = new Map();
  const parent = { postMessage: (message) => sent.push(message) };
  const fakeWindow = {
    parent,
    location: { origin: 'http://same-origin.test' },
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: () => {},
  };
  installParentBridge(fakeWindow, { prepare: async () => ({}), apply: async () => {} });
  await listeners.get('message')({
    origin: fakeWindow.location.origin,
    source: parent,
    data: { ...envelope('APPLY_REVISION'), request_id: 'request_old' },
  });
  assert.equal(sent.at(-1).type, 'ROBCRAFT_ERROR');
  assert.match(sent.at(-1).payload.message, /не подготовлена|устарела/);
});

test('camera control is revision-bound and reports pointer-lock state', async () => {
  const sent = [];
  const listeners = new Map();
  const parent = { postMessage: (message) => sent.push(message) };
  const fakeWindow = {
    parent,
    location: { origin: 'http://same-origin.test' },
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: () => {},
  };
  installParentBridge(fakeWindow, {
    prepare: async () => ({}),
    apply: async () => {},
    setCameraMode: async (mode) => ({ mode, reason: 'USER_REQUEST', pointerLocked: true }),
    getCameraState: () => ({ mode: 'AUTOPILOT', pointerLocked: false }),
  });
  const scenario = { revision_id: revision };
  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('LOAD_SCENARIO', { scenario_spec: scenario }) });
  await listeners.get('message')({ origin: fakeWindow.location.origin, source: parent, data: envelope('APPLY_REVISION') });
  await listeners.get('message')({
    origin: fakeWindow.location.origin,
    source: parent,
    data: envelope('SET_CAMERA_MODE', { mode: 'MANUAL_FIRST_PERSON' }),
  });
  assert.deepEqual(sent.at(-1).payload, {
    mode: 'MANUAL_FIRST_PERSON', reason: 'USER_REQUEST', pointer_locked: true,
  });
});
