import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { economicsRunView } from '../src/economicsRunModel.js';

test('historical legacy runs stay on the snapshot viewer', () => {
  const view = economicsRunView({
    run_kind: 'FULL_ANALYSIS',
    versions: { economics: 'legacy-economics-v1' },
    economics_runtime: {
      economics_version: 'legacy-economics-v1',
      viewer_version: 'legacy-snapshot-viewer-v1',
      replay_mode: 'SAVED_SNAPSHOT_ONLY',
      migration_notice: 'No recalculation',
    },
  });
  assert.deepEqual(view, {
    viewer: 'LEGACY_SNAPSHOT', label: 'Legacy snapshot', notice: 'No recalculation',
  });
});

test('v2 runs select the commercial scenarios viewer and mismatches fail closed', () => {
  const run = {
    run_kind: 'FULL_ANALYSIS',
    versions: { economics: 'economics-runtime-v2' },
    economics_runtime: {
      economics_version: 'economics-runtime-v2',
      viewer_version: 'commercial-scenarios-viewer-v2',
      replay_mode: 'DETERMINISTIC_V2',
      migration_notice: 'v2',
    },
  };
  assert.equal(economicsRunView(run).viewer, 'COMMERCIAL_SCENARIOS_V2');
  assert.throws(() => economicsRunView({ ...run, versions: { economics: 'unknown' } }), /MISMATCH/);
});

test('new UI cannot create a legacy analysis run from the historical viewer', () => {
  const source = fs.readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /\/api\/calculate|\/api\/projects\/\$\{activeProject\.id\}\/analysis-runs/);
  assert.match(source, /HistoricalRunViewer/);
  assert.match(source, /<EconomicsInputsV2/);
});
