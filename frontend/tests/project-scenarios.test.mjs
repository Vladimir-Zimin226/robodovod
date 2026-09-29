import test from 'node:test';
import assert from 'node:assert/strict';
import { canonicalJson, editScenarioInput, inputDigest, scenarioInputError, metricText } from '../src/projectScenarioModel.js';

test('digest binds exact nested input, sources and zero without mutating original', async () => {
  const original = { raas_mode: 'PERCENT', raas_percent_monthly: '2', field_sources: {}, unknown: null };
  const edited = editScenarioInput(original, 'raas_percent_monthly', '0');
  assert.equal(edited.raas_mode, 'PERCENT');
  assert.equal(original.raas_percent_monthly, '2');
  assert.notEqual(await inputDigest(original), await inputDigest(edited));
  assert.equal(await inputDigest(original), await inputDigest({ unknown: null, field_sources: {}, raas_percent_monthly: '2', raas_mode: 'PERCENT' }));
  assert.equal(canonicalJson({ x: null }), '{"x":null}');
});

test('unknown remains empty, invalid finance does not become zero, unavailable payback is explicit', () => {
  assert.equal(scenarioInputError({ raas_percent_monthly: '', purchase_price_override_gross: null }), '');
  for (const input of [{ raas_percent_monthly: '-1' }, { raas_percent_monthly: '101' }, { horizon_years: '4' }, { horizon_years: '5.5' }, { discount_rate: '2' }]) assert.ok(scenarioInputError(input));
  assert.equal(scenarioInputError({ raas_percent_monthly: '0' }), '');
  assert.equal(metricText({ status: 'NOT_REACHED', value: null }), 'Окупаемость не достигнута');
});
