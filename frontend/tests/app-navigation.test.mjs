import test from 'node:test';
import assert from 'node:assert/strict';

import { phaseFromHash, phaseHash } from '../src/appNavigation.js';

test('process, calculation and catalog have distinct browser routes', () => {
  assert.equal(phaseHash('process'), '#process');
  assert.equal(phaseHash('intake'), '#calculation');
  assert.equal(phaseHash('catalog'), '#catalog');
  assert.equal(phaseFromHash('#process'), 'process');
  assert.equal(phaseFromHash('#calculation'), 'intake');
  assert.equal(phaseFromHash('#catalog'), 'catalog');
});

test('a result link restores only with an in-memory result', () => {
  assert.equal(phaseFromHash('#results'), 'onboarding');
  assert.equal(phaseFromHash('#results', true), 'results');
  assert.equal(phaseFromHash('#unknown'), 'onboarding');
  assert.throws(() => phaseHash('unknown'), /Неизвестная страница/);
});
