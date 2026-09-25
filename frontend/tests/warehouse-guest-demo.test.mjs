import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import demo from '../src/warehouseGuestDemo.json' with { type: 'json' };

test('guest warehouse capture includes baseline, six branches and sensitivity with honest gates', () => {
  assert.equal(demo.schema_version, 'warehouse-guest-demo-v1');
  assert.equal(demo.scenarios.length, 6);
  assert.equal(demo.sensitivity.length, 6);
  assert.equal(demo.c05, 'NEEDS_VALIDATION');
  assert.equal(demo.procurement, 'UNVERIFIED');
  assert.equal(demo.capacity.value.selected_fleet, 18);
  assert.ok(demo.scenarios.every((item) => item.annual_ledgers.length > 0));
});

test('guest screen does not submit or persist user data', async () => {
  const source = await readFile(new URL('../src/components/GuestWarehouseDemo.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /fetch\(|localStorage|sessionStorage|POST/);
  assert.match(source, /не отправляются/);
});
