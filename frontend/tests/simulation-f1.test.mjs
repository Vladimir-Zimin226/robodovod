import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { visualExportMetadata } from '../src/simulationSvgExport.js';
import { physicalRunOption, physicalInputs } from '../src/physicalScenario.js';

const { request, report } = JSON.parse(await readFile(new URL('./fixtures/warehouse-2d-stage3.json', import.meta.url)));

test('visual export preserves exact saved physical inputs, C23 and frame binding without mutation', () => {
  const original = JSON.stringify({ request, report });
  const meta = visualExportMetadata(request, report, 'run.saved', 5e6, request.scenario_spec.zones[0].zone_id, '2026-09-26T00:00:00Z');
  assert.equal(meta.report_content_digest, report.replay.report_content_digest);
  assert.equal(meta.scenario_spec_digest, report.replay.scenario_spec_digest);
  assert.equal(meta.capacity_run_id, request.scenario_spec.analysis.capacity_run_id);
  assert.equal(meta.simulation_time_us, 5e6);
  assert.deepEqual(meta.request, request); assert.deepEqual(meta.report, report);
  assert.equal(JSON.stringify({ request, report }), original);
  assert.ok(physicalInputs(request.scenario_spec).some((line) => line.includes('120 m')));
  assert.throws(() => visualExportMetadata(request, { ...report, request_id: 'foreign' }, 'run.saved', 0, null, ''), /не связан/);
});

test('saved physical selector accepts supported snapshots and keeps run identity', () => {
  const spec = structuredClone(request.scenario_spec);
  const run = { id: 'saved-run', run_kind: 'FULL_ANALYSIS', scenario_spec_snapshot: spec,
    result_snapshot: { schema_version: 'economics-partial-result-v1', capacity_run_id: spec.analysis.capacity_run_id,
      project_id: spec.analysis.project_id, tenant_id: spec.analysis.tenant_id } };
  const option = physicalRunOption(run);
  assert.equal(option.id, run.id); assert.deepEqual(option.request.scenario_spec, spec);
  assert.ok(option.label.includes('120 m'));
  assert.equal(physicalRunOption({ ...run, scenario_spec_snapshot: { schema_version: 'scenario-spec-partial-v1' } }), null);
  assert.equal(physicalRunOption({ ...run, result_snapshot: { ...run.result_snapshot, tenant_id: 'foreign' } }), null);
});
