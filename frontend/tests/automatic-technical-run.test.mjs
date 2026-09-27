import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { automaticTechnicalRun } from '../src/automaticTechnicalRun.js';

const spec = JSON.parse(await readFile(new URL('../../contracts/fixtures/scenario-spec-v2.capacity-only-cleaner.golden.json', import.meta.url), 'utf8'));
const run = { id: 'saved.technical', run_kind: 'FULL_ANALYSIS', scenario_spec_snapshot: spec,
  result_snapshot: { schema_version: 'economics-partial-result-v1', capacity_run_id: spec.analysis.capacity_run_id,
    project_id: spec.analysis.project_id, tenant_id: spec.analysis.tenant_id },
  input_snapshot: { capacity_run_id: spec.analysis.capacity_run_id, economics: { timezone: 'Europe/Moscow', start_seconds_from_midnight: '32400' } } };
const options = { project: { id: spec.analysis.project_id, scenarios: [{ slot: 'BASE', id: 'base' }] },
  capacityRequest: { input_revision: spec.analysis.input_revision, process: { scope: 'CLEANING_AREA', role_refs: [] } },
  capacityRunId: spec.analysis.capacity_run_id, startTime: '09:00', timezone: 'Europe/Moscow' };
const response = (payload, ok = true) => ({ ok, json: async () => payload });
globalThis.document = { cookie: 'robodovod_csrf=test-token' };

test('automatic startup shares a save under simultaneous mounts and sends the same capacity binding', async () => {
  let writes = 0;
  const request = async (url, init) => {
    if (!init.method) return response({ items: [] });
    writes++;
    assert.equal(init.headers['X-CSRF-Token'], 'test-token');
    const body = JSON.parse(init.body);
    assert.equal(body.capacity_run_id, options.capacityRunId);
    assert.equal(body.input.start_seconds_from_midnight, '32400');
    assert.equal(body.input.timezone, 'Asia/Sakhalin');
    return response(run);
  };
  const selected = { ...options, timezone: 'Asia/Sakhalin' };
  const [first, second] = await Promise.all([automaticTechnicalRun(selected, request), automaticTechnicalRun(selected, request)]);
  assert.equal(first.id, run.id); assert.equal(second.id, run.id); assert.equal(writes, 1);
});

test('reopening reuses a matching saved physical run without writing', async () => {
  const request = async (url, init) => {
    assert.equal(init.method, undefined);
    return response(url.endsWith(`/${run.id}`) ? run : { items: [{ id: run.id, run_kind: 'FULL_ANALYSIS', status: 'SUCCEEDED' }] });
  };
  assert.equal((await automaticTechnicalRun(options, request)).id, run.id);
});

test('a failed save can retry and invalid model time never writes', async () => {
  const selected = { ...options, startTime: '07:00' };
  let writes = 0;
  const request = async (url, init) => {
    if (!init.method) return response({ items: [] });
    writes++;
    return writes === 1 ? response({ detail: 'temporarily unavailable' }, false) : response(run);
  };
  await assert.rejects(automaticTechnicalRun(selected, request), /temporarily unavailable/);
  assert.equal((await automaticTechnicalRun(selected, request)).id, run.id);
  assert.equal(writes, 2);
  await assert.rejects(automaticTechnicalRun({ ...options, startTime: '25:01' }, request), /начало/);
  assert.equal(writes, 2);
});
