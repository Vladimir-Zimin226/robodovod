import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import demo from '../src/warehouseGuestDemo.json' with { type: 'json' };
import guestPackage from '../src/warehouseGuestPackage.json' with { type: 'json' };

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
  assert.match(source, /Simulation2DReport request=\{simulation\.request\} initialReport=\{simulation\.report\}/);
  assert.match(source, /report\.pdf/);
  assert.match(source, /evidence\.zip/);
  assert.doesNotMatch(source, /bg-white|text-slate/);
});

test('guest package presents one authored warehouse scenario across economics and simulation', () => {
  assert.equal(guestPackage.schema_version, 'warehouse-pallet-demo-v1');
  assert.deepEqual(guestPackage.demo, demo);
  assert.equal(guestPackage.simulation.report.schema_version, 'simulation-report-v3');
  assert.equal(guestPackage.simulation.report.workload.daily_units, '2000');
  assert.equal(guestPackage.simulation.report.workload.fleet_units, demo.capacity.value.selected_fleet);
  assert.equal(guestPackage.simulation.request.scenario_spec.routes[0].one_way_distance.value, '120');
  assert.equal(guestPackage.simulation.report.scenario_revision_id, guestPackage.bindings.scenario_revision_id);
  assert.equal(guestPackage.simulation.report.replay.report_content_digest, guestPackage.bindings.simulation_report_digest);
  assert.equal(guestPackage.chain.filter((item) => item.status === 'MODELED').length, 1);
  assert.ok(guestPackage.simulation.report.stages.every((item) => item.status === 'EXTERNAL_BOUNDARY'));
});
