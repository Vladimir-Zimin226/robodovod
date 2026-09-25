import test from 'node:test';
import assert from 'node:assert/strict';
import { formatModelClock, modelTimezone, MODEL_START_SECONDS } from '../src/simulationDefaults.js';
import { qualifiedWarehouseStages } from '../src/warehouseSimulationChain.js';

test('new model defaults to local Monday 09 without replacing a saved timezone', () => {
  assert.equal(MODEL_START_SECONDS, 32400);
  assert.equal(modelTimezone({ profile: { timezone: 'Asia/Sakhalin' } }, 'Europe/Moscow'), 'Asia/Sakhalin');
  assert.equal(modelTimezone({}, 'Europe/Moscow'), 'Europe/Moscow');
  assert.equal(modelTimezone({}, 'not-a-zone'), '');
  assert.equal(formatModelClock({ seconds_from_midnight: 86340, timezone: 'Asia/Sakhalin' }, 120_000_000),
    'вторник, 00:01 · Asia/Sakhalin');
});

test('warehouse stages require confirmed linked volumes, separate rate and capacity', () => {
  const chain = {
    schema_version: 'warehouse-chain-v1', version: 1,
    flows: [
      { code: 'picking_lines', value: '11000', confirmed: true, resource_ids: ['picker'], solution: 'MANUAL' },
      { code: 'packaging', value: '220', confirmed: true, resource_ids: ['packer'], solution: 'MANUAL' },
    ],
    resources: [
      { resource_id: 'picker', kind: 'STAFF', amount: '2', confirmed: true },
      { resource_id: 'packer', kind: 'STAFF', amount: '1', confirmed: true },
    ],
    conversions: [
      { from_code: 'picking_lines', to_code: 'packaging', factor: '0.02', confirmed: true },
      { from_code: 'packaging', to_code: 'shipping', factor: '1', confirmed: true },
    ],
  };
  const stages = qualifiedWarehouseStages(chain, { PICKING: '100', PACKAGING: '50' }, 220);
  assert.deepEqual(stages.map((stage) => stage.stage), ['PICKING', 'PACKAGING']);
  assert.equal(stages[0].units_per_pallet, '50');
  assert.equal(stages[1].resource_kind, 'HUMAN');
  assert.deepEqual(qualifiedWarehouseStages(chain, { PICKING: '100', PACKAGING: '50' }, 200), []);
  assert.deepEqual(qualifiedWarehouseStages(chain, {}, 220), []);
});
