import test from 'node:test';
import assert from 'node:assert/strict';
import { ROLE_LABELS, roleLabel } from '../src/roleLabels.js';

test('every supported role has a distinct human label and new functions are separate', () => {
  assert.equal(Object.keys(ROLE_LABELS).length, 29);
  assert.equal(new Set(Object.values(ROLE_LABELS)).size, Object.keys(ROLE_LABELS).length);
  assert.equal(roleLabel('control_operator'), 'Диспетчер роботов');
  assert.equal(roleLabel('tech_support'), 'Технический специалист');
  assert.notEqual(roleLabel('forklift_driver'), roleLabel('picker'));
});
