import test from 'node:test';
import assert from 'node:assert/strict';

import {
  WAREHOUSE_ECONOMICS_DEMO, applyWarehouseEconomicsDemo, chooseUserField,
  confirmAllEconomicsAssumptions, editEconomicsField, proposeDemoField,
} from '../src/economicsDemoAssumptions.js';
import { buildPartialEconomicsRunRequest } from '../src/economicsInputV2.js';

const fields = [
  ['Покупка', 'implementationCost', 'implementation_cost_total_gross'],
  ['Покупка', 'sharedSiteCapital', 'shared_site_capital_gross'],
];
const initial = { implementationCost: '700000', sharedSiteCapital: '', sources: {}, assumptions: {}, userValues: {} };

test('offered value has stable source and choosing user data restores the entered number', () => {
  const offered = proposeDemoField(initial, 'implementationCost', 'implementation_cost_total_gross');
  assert.equal(offered.implementationCost, '500000');
  assert.equal(offered.assumptions.implementation_cost_total_gross.confirmed, false);
  assert.equal(offered.assumptions.implementation_cost_total_gross.published_on, '2026-09-25');
  assert.equal(offered.assumptions.implementation_cost_total_gross.template_id, WAREHOUSE_ECONOMICS_DEMO.schema_version);
  const restored = chooseUserField(offered, 'implementationCost', 'implementation_cost_total_gross');
  assert.equal(restored.implementationCost, '700000');
  assert.equal(restored.sources.implementation_cost_total_gross, 'USER');
});

test('other processes never receive warehouse demo numbers', () => {
  const offered = proposeDemoField(initial, 'implementationCost', 'implementation_cost_total_gross', { enableTemplate: false });
  assert.equal(offered.implementationCost, '700000');
  assert.equal(offered.assumptions.implementation_cost_total_gross, null);
  const custom = editEconomicsField(offered, 'implementationCost', 'implementation_cost_total_gross', '700000', { enableTemplate: false });
  assert.equal(custom.assumptions.implementation_cost_total_gross.template_id, null);
});

test('demo zero, empty and range retain distinct meanings; edit invalidates old confirmation', () => {
  const proposed = applyWarehouseEconomicsDemo(initial, fields);
  assert.equal(proposed.sharedSiteCapital, '0');
  const confirmed = confirmAllEconomicsAssumptions(proposed);
  assert.equal(confirmed.assumptions.implementation_cost_total_gross.confirmed, true);
  const edited = editEconomicsField(confirmed, 'implementationCost', 'implementation_cost_total_gross', '600000');
  assert.equal(edited.assumptions.implementation_cost_total_gross.confirmed, false);
  assert.equal(edited.assumptions.implementation_cost_total_gross.template_id, null);
  const cleared = editEconomicsField(edited, 'implementationCost', 'implementation_cost_total_gross', '');
  assert.equal(cleared.assumptions.implementation_cost_total_gross, null);
  const range = editEconomicsField(confirmed, 'implementationCost', 'implementation_cost_total_gross', '500000..800000');
  assert.equal(range.implementationCost, '500000..800000');
  assert.equal(range.assumptions.implementation_cost_total_gross.confirmed, false);
});

test('versioned request carries confirmed evidence and a source run for an immutable revision', () => {
  const proposed = confirmAllEconomicsAssumptions(applyWarehouseEconomicsDemo(initial, fields));
  const request = buildPartialEconomicsRunRequest({ values: { ...proposed, capacityRunId: 'capacity.1' },
    capacityRequest: { input_revision: 'revision.1', process: { scope: 'TRANSPORT_CYCLE', role_refs: ['role.driver'] } },
    project: { id: 'project.1' }, scenario: { id: 'scenario.1' }, sourceRunId: 'economics.old' });
  assert.equal(request.input.schema_version, 'economics-explicit-inputs-v5');
  assert.equal(request.source_run_id, 'economics.old');
  assert.equal(request.input.implementation_cost_total_gross, '500000');
  assert.equal(request.input.shared_site_capital_gross, '0');
  assert.equal(request.input.assumption_evidence.implementation_cost_total_gross.confirmed, true);
});
