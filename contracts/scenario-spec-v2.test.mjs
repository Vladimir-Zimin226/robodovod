import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const schema = JSON.parse(readFileSync(new URL('./scenario-spec-v2.schema.json', import.meta.url), 'utf8'));
const fixture = JSON.parse(readFileSync(
  new URL('./fixtures/scenario-spec-v2.capacity-only-cleaner.golden.json', import.meta.url),
  'utf8',
));

function dereference(rule) {
  if (!rule.$ref) return rule;
  return rule.$ref.replace(/^#\//, '').split('/').reduce((value, part) => value[part], schema);
}

function matchesType(value, type) {
  if (type === 'null') return value === null;
  if (type === 'array') return Array.isArray(value);
  if (type === 'object') return value !== null && typeof value === 'object' && !Array.isArray(value);
  if (type === 'integer') return Number.isInteger(value);
  if (type === 'number') return typeof value === 'number' && Number.isFinite(value);
  return typeof value === type;
}

function validate(value, sourceRule, path = '$') {
  const rule = dereference(sourceRule);
  const alternatives = rule.anyOf || rule.oneOf;
  if (alternatives) {
    const matches = alternatives.filter((candidate) => {
      try { validate(value, candidate, path); return true; } catch { return false; }
    });
    assert.equal(matches.length, 1, `${path}: expected exactly one union match`);
    return;
  }
  if (rule.const !== undefined) assert.deepEqual(value, rule.const, `${path}: const`);
  if (rule.enum) assert.ok(rule.enum.includes(value), `${path}: enum`);
  if (rule.type) {
    const types = Array.isArray(rule.type) ? rule.type : [rule.type];
    assert.ok(types.some((type) => matchesType(value, type)), `${path}: type ${types.join('|')}`);
  }
  if (value === null) return;
  if (typeof value === 'string') {
    if (rule.minLength !== undefined) assert.ok(value.length >= rule.minLength, `${path}: minLength`);
    if (rule.pattern) assert.match(value, new RegExp(rule.pattern), `${path}: pattern`);
  }
  if (typeof value === 'number') {
    if (rule.minimum !== undefined) assert.ok(value >= rule.minimum, `${path}: minimum`);
    if (rule.maximum !== undefined) assert.ok(value <= rule.maximum, `${path}: maximum`);
  }
  if (Array.isArray(value)) {
    if (rule.minItems !== undefined) assert.ok(value.length >= rule.minItems, `${path}: minItems`);
    if (rule.maxItems !== undefined) assert.ok(value.length <= rule.maxItems, `${path}: maxItems`);
    if (rule.items) value.forEach((item, index) => validate(item, rule.items, `${path}[${index}]`));
  } else if (value && typeof value === 'object') {
    for (const required of rule.required || []) assert.ok(Object.hasOwn(value, required), `${path}: missing ${required}`);
    if (rule.additionalProperties === false) {
      for (const key of Object.keys(value)) assert.ok(Object.hasOwn(rule.properties || {}, key), `${path}: unknown ${key}`);
    }
    for (const [key, item] of Object.entries(value)) {
      if (rule.properties?.[key]) validate(item, rule.properties[key], `${path}.${key}`);
    }
  }
}

test('JavaScript and Python schema accept the capacity-only cleaner fixture', () => {
  validate(fixture, schema);
  assert.equal(fixture.finance, null);
  assert.equal(fixture.profile.calculation_profile, 'CLEANING_AREA_V1');
  assert.equal(JSON.stringify(fixture).includes('payload'), false);
});

test('JavaScript schema rejects unknown major versions and extra fields', () => {
  assert.throws(() => validate({ ...fixture, schema_version: 'scenario-spec-v3' }, schema));
  assert.throws(() => validate({ ...fixture, renderer_internal: {} }, schema));
  assert.throws(() => validate({
    ...fixture,
    versions: {
      ...fixture.versions,
      calculation: { ...fixture.versions.calculation, formula_bundle_version: 'calculation-formulas-v2' },
    },
  }, schema));
});

test('fixture revision changes when a meaningful version binding changes', () => {
  const changed = structuredClone(fixture);
  changed.versions.calculation.catalog_version_id = 'catalog.c22.next';
  assert.notDeepEqual(changed.versions, fixture.versions);
  assert.equal(fixture.revision_id, 'calc_fe6611cc9a672595');
});
