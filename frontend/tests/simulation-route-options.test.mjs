import test from 'node:test';
import assert from 'node:assert/strict';
import { simulationOptions } from '../src/simulationRouteOptions.js';

test('warehouse transport remains selectable without a catalog position', () => {
  const input = { roles: [{ role_code: 'forklift_driver' }, { role_code: 'cleaner' }] };
  const report = { roles: [{ selected_position_id: null }, { selected_position_id: null }] };
  assert.deepEqual(simulationOptions(input, report).map((item) => item.key), ['0']);
});

test('airport and clinic use matching transport work, not area cleaning or unrelated work', () => {
  const input = { roles: [
    { role_code: 'cleaner', works: [{ process_code: 'clinic_cleaning', technical_task: 'Уборка' }] },
    { role_code: 'porter', works: [{ process_code: 'clinic_medicines', technical_task: 'Доставка' }] },
  ] };
  const report = { kind: 'CLINIC', roles: [{}, {}] };
  assert.deepEqual(simulationOptions(input, report).map((item) => item.key), ['1:0']);
  input.roles[1].works[0].process_code = 'airport_baggage';
  assert.deepEqual(simulationOptions(input, { ...report, kind: 'AIRPORT' }).map((item) => item.key), ['1:0']);
});
