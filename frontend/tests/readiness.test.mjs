import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('calculation requests readiness independently and preserves provenance', async () => {
  const source = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.match(source, /\/api\/readiness/);
  assert.match(source, /parameter_values/);
  assert.match(source, /parameter_provenance/);
  assert.match(source, /readiness_report/);
});


test('dashboard exposes status, dimensions, architecture and preconditions', async () => {
  const source = await readFile(new URL('../src/components/DashboardOverview.jsx', import.meta.url), 'utf8');
  assert.match(source, /readinessReport\.overall_status/);
  assert.match(source, /report\.dimensions\.map/);
  assert.match(source, /architecture_candidates/);
  assert.match(source, /report\.preconditions/);
  assert.match(source, /Нужна проверка/);
});
