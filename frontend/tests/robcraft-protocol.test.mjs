import test from 'node:test';
import assert from 'node:assert/strict';

import { negotiateScenarioSpec, parentMessage, parseRobCraftMessage } from '../src/robcraftProtocol.js';

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

test('negotiates ScenarioSpec versions without an implicit downgrade', () => {
  const v1 = { schema_version: 'scenario-spec-v1', revision_id: revision };
  const v2 = { schema_version: 'scenario-spec-v2', revision_id: revision };
  assert.equal(negotiateScenarioSpec(v1, ['scenario-spec-v1']), v1);
  assert.equal(negotiateScenarioSpec(v2, ['scenario-spec-v1', 'scenario-spec-v2']), v2);
  assert.throws(() => negotiateScenarioSpec(v2, ['scenario-spec-v1']), /не объявил поддержку/);
  assert.throws(() => negotiateScenarioSpec({ ...v2, schema_version: 'scenario-spec-v3' }, ['scenario-spec-v3']), /Неподдерживаемая версия/);
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

test('accepts an honest renderer report and rejects fake SLA or extra finance', () => {
  const payload = {
    schema_version: 'robcraft-renderer-report-v1', status: 'LOCAL_VISUAL_OBSERVATION_ONLY',
    bindings: { scenario_revision_id: revision, scenario_spec_version: 'scenario-spec-v2', scenario_seed: 'scenario-0123456789abcdef', authoritative_report_id: 'report.test', authoritative_report_digest: `sha256:${'a'.repeat(64)}`, scheduler_seed: 42 },
    versions: { renderer_engine_version: 'robcraft-time-step-v1', event_profile_version: 'robcraft-visual-events-v1', report_version: 'robcraft-renderer-report-v1' },
    measurement_basis: { kind: 'LIVE_RENDERER_WINDOW', elapsed_seconds: '12.5', operating_hours_per_day: '8', operating_window_refs: ['window.shift'], warmup_days: null, measurement_days: null },
    geometry: { source: 'PROVIDED', status: 'MODIFIED', base_revision_id: revision, economics_status: 'UNCHANGED', analytical_route_ref: 'route.main', analytical_distance_value: '123', analytical_distance_unit: 'm' },
    observed: { completed_units: '10', throughput_units_per_hour: '2880', throughput_unit: 'unit/h', queued_jobs: 1, average_queue_seconds: '2.5' },
    utilization: { moving_percent: '50', moving_basis: 'ROBOT_MOVING_TIME_OVER_RENDERER_ELAPSED_FLEET_TIME', productive_percent: null, productive_status: 'NOT_EVALUATED_LOCAL_TIME_STEP' },
    energy: { value: '7', unit: 'ARBITRARY_RENDERER_UNIT', economics_status: 'NOT_COMPARABLE_TO_RUB_OR_KWH' },
    model_status: { sla: 'NOT_EVALUATED_USE_C23_REPORT', failures: 'VISUAL_DEMO_ONLY_NOT_ANALYTICAL', charging: 'VISUAL_DEMO_ONLY_NOT_ANALYTICAL', engineering_claim: 'CONCEPTUAL_VISUALIZATION_NOT_CERTIFICATION' },
    limitations: ['use-c23-report-for-capacity-queue-sla-and-finance'],
  };
  const message = { schema_version: 'robcraft-message-v1', type: 'ROBCRAFT_REPORT', revision_id: revision, request_id: 'request_report', payload };
  assert.equal(parseRobCraftMessage(message).payload.status, 'LOCAL_VISUAL_OBSERVATION_ONLY');
  assert.throws(() => parseRobCraftMessage({ ...message, payload: { ...payload, model_status: { ...payload.model_status, sla: 'PASS' } } }), /SLA\/engineering/);
  assert.throws(() => parseRobCraftMessage({ ...message, payload: { ...payload, finance: {} } }), /неизвестные поля/);
  assert.throws(() => parseRobCraftMessage({ ...message, revision_id: 'calc_ffffffffffffffff' }), /не связан/);
});
