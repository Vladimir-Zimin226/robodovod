import test from 'node:test';
import assert from 'node:assert/strict';

import { parentMessage, parseRobCraftMessage } from '../src/robcraftProtocol.js';

const revision = 'calc_0123456789abcdef';

test('accepts the strict ready and two-phase loaded envelopes', () => {
  assert.equal(parseRobCraftMessage({
    schema_version: 'robcraft-message-v1',
    type: 'ROBCRAFT_READY',
    revision_id: null,
    request_id: null,
    payload: { capabilities: ['scenario-spec-v1', 'two-phase-apply'] },
  }).type, 'ROBCRAFT_READY');

  assert.equal(parseRobCraftMessage({
    schema_version: 'robcraft-message-v1',
    type: 'SCENARIO_LOADED',
    revision_id: revision,
    request_id: 'request_1',
    payload: { status: 'APPLIED' },
  }).payload.status, 'APPLIED');
});

test('rejects unknown fields and versions', () => {
  assert.throws(() => parseRobCraftMessage({
    schema_version: 'robcraft-message-v2', type: 'ROBCRAFT_READY',
    revision_id: null, request_id: null, payload: {}, surprise: true,
  }), /неизвестные поля/);
});

test('creates a revision-bound parent message', () => {
  const message = parentMessage('APPLY_REVISION', revision, 'request_2');
  assert.deepEqual(message, {
    schema_version: 'robcraft-message-v1', type: 'APPLY_REVISION',
    revision_id: revision, request_id: 'request_2', payload: {},
  });
});

test('accepts a revisionless bootstrap error for WebGL fallback', () => {
  const message = parseRobCraftMessage({
    schema_version: 'robcraft-message-v1', type: 'ROBCRAFT_ERROR',
    revision_id: null, request_id: null,
    payload: { code: 'WEBGL_UNAVAILABLE', message: 'WebGL unavailable' },
  });
  assert.equal(message.payload.code, 'WEBGL_UNAVAILABLE');
});

test('validates camera-mode notifications', () => {
  const message = parseRobCraftMessage({
    schema_version: 'robcraft-message-v1', type: 'CAMERA_MODE_CHANGED',
    revision_id: revision, request_id: 'request_camera',
    payload: { mode: 'MANUAL_FIRST_PERSON', reason: 'USER_REQUEST', pointer_locked: true },
  });
  assert.equal(message.payload.mode, 'MANUAL_FIRST_PERSON');
  assert.throws(() => parseRobCraftMessage({
    ...message, payload: { ...message.payload, mode: 'EDITOR' },
  }), /Неизвестный режим/);
});

test('validates editor and revision-bound ScenePatch notifications', () => {
  const editor = parseRobCraftMessage({
    schema_version: 'robcraft-message-v1', type: 'EDITOR_MODE_CHANGED', revision_id: revision, request_id: 'request_editor',
    payload: { enabled: true, scene_status: 'MODIFIED', simulation_paused: true },
  });
  assert.equal(editor.payload.simulation_paused, true);
  const patch = parseRobCraftMessage({
    schema_version: 'robcraft-message-v1', type: 'SCENE_PATCH_CHANGED', revision_id: revision, request_id: 'request_editor',
    payload: { format: 'robcraft-scene-patch-v1', base_revision_id: revision, visual_fingerprint: 'visual_1234abcd', zone_id: 'receiving', status: 'MODIFIED', economics_status: 'UNCHANGED', summary: { objects: 1, created: 0, deleted: 0, robots: 0 } },
  });
  assert.equal(patch.payload.status, 'MODIFIED');
  assert.throws(() => parseRobCraftMessage({ ...patch, payload: { ...patch.payload, economics_status: 'RECALCULATED' } }), /ScenePatch/);
});
