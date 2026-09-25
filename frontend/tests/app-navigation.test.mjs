import test from 'node:test';
import assert from 'node:assert/strict';

import { phaseFromHash, phaseHash } from '../src/appNavigation.js';

test('service assistant, calculation and catalog have distinct browser routes', () => {
  assert.equal(phaseHash('process'), '#assistant');
  assert.equal(phaseHash('intake'), '#calculation');
  assert.equal(phaseHash('catalog'), '#catalog');
  assert.equal(phaseHash('model'), '#model');
  assert.equal(phaseHash('expert'), '#roboexpert');
  assert.equal(phaseHash('economics'), '#economics');
  assert.equal(phaseHash('reports'), '#reports');
  assert.equal(phaseFromHash('#assistant'), 'process');
  assert.equal(phaseFromHash('#process'), 'process');
  assert.equal(phaseFromHash('#calculation'), 'intake');
  assert.equal(phaseFromHash('#catalog'), 'catalog');
  assert.equal(phaseFromHash('#model'), 'model');
  assert.equal(phaseFromHash('#roboexpert'), 'expert');
  assert.equal(phaseFromHash('#economics'), 'economics');
  assert.equal(phaseFromHash('#reports'), 'reports');
  assert.equal(phaseFromHash('#report'), 'reports');
  assert.equal(phaseFromHash('#variants'), 'expert');
  assert.equal(phaseFromHash('#scenarios'), 'expert');
});

test('a result link restores only with an in-memory result', () => {
  assert.equal(phaseFromHash('#results'), 'onboarding');
  assert.equal(phaseFromHash('#results', true), 'results');
  assert.equal(phaseFromHash('#unknown'), 'onboarding');
  assert.throws(() => phaseHash('unknown'), /Неизвестная страница/);
});
