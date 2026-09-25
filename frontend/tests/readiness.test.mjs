import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('new calculation starts from the v2 intake while historical readiness remains a saved result', async () => {
  const source = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.match(source, /<IntakeScreen/);
  assert.match(source, /HistoricalRunViewer/);
  assert.doesNotMatch(source, /\/api\/readiness|\/api\/calculate/);
});


test('dashboard exposes status, dimensions, architecture and preconditions', async () => {
  const source = await readFile(new URL('../src/components/DashboardOverview.jsx', import.meta.url), 'utf8');
  assert.match(source, /readinessReport\.overall_status/);
  assert.match(source, /report\.dimensions\.map/);
  assert.match(source, /architecture_candidates/);
  assert.match(source, /report\.preconditions/);
  assert.match(source, /Нужна проверка/);
});
