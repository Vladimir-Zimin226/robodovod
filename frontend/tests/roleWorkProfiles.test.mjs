import test from 'node:test';
import assert from 'node:assert/strict';
import { buildRoleWorkProfiles, primaryWorkEvidence } from '../src/roleWorkProfiles.js';

test('measured primary role keeps its source and unconfirmed secondary role does not claim savings', () => {
  const values = {
    robotizableShare: '0.4', manualUnitsPerShift: '45', residualOperations: 'Manual inspection remains',
    roleWorkProfiles: {
      driver: { source: 'USER', basis: 'Time study 2026-10-19, shift A', confirmed: true },
    },
  };
  const profiles = buildRoleWorkProfiles(values, ['driver', 'loader'], 'driver');
  assert.deepEqual(primaryWorkEvidence(values, 'driver'), {
    source: 'USER', basis: 'Time study 2026-10-19, shift A', confirmed: true,
  });
  assert.equal(profiles[0].robotizable_fraction, '0.4');
  assert.equal(profiles[0].manual_units_per_shift, '45');
  assert.equal(profiles[0].source, 'USER');
  assert.equal(profiles[1].robotizable_fraction, '0');
  assert.equal(profiles[1].manual_units_per_shift, null);
  assert.equal(profiles[1].source, 'ASSUMPTION');
  assert.equal(profiles[1].confirmed, false);
});

test('positive secondary share needs its own throughput and evidence', () => {
  const values = {
    robotizableShare: '0.4', manualUnitsPerShift: '45', residualOperations: 'Manual inspection remains',
    roleWorkProfiles: { loader: { fraction: '0.25', source: 'USER', confirmed: true } },
  };
  const loader = buildRoleWorkProfiles(values, ['driver', 'loader'], 'driver')[1];
  assert.equal(loader.robotizable_fraction, '0.25');
  assert.equal(loader.manual_units_per_shift, null);
  assert.equal(loader.residual_operations, '');
  assert.equal(loader.basis, '');
  assert.equal(loader.confirmed, true);
});

test('primary assumption cannot become confirmed without an explicit choice', () => {
  const evidence = primaryWorkEvidence({ roleWorkProfiles: {} }, 'driver');
  assert.equal(evidence.source, 'ASSUMPTION');
  assert.equal(evidence.confirmed, false);
  assert.match(evidence.basis, /допущение/);
});
