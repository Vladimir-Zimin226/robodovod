import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const schema = JSON.parse(readFileSync(new URL('./scenario-spec-v1.schema.json', import.meta.url), 'utf8'));
const fixture = JSON.parse(readFileSync(new URL('./fixtures/scenario-spec-v1.golden.json', import.meta.url), 'utf8'));
const economicsV2Fixture = JSON.parse(readFileSync(
  new URL('./fixtures/scenario-spec-v1.economics-v2.golden.json', import.meta.url),
  'utf8',
));

function dereference(rule) {
  if (!rule.$ref) return rule;
  const parts = rule.$ref.replace(/^#\//, '').split('/');
  return parts.reduce((value, part) => value[part], schema);
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
  if (rule.oneOf) {
    const valid = rule.oneOf.filter((candidate) => {
      try { validate(value, candidate, path); return true; } catch { return false; }
    });
    assert.equal(valid.length, 1, `${path}: expected exactly one oneOf match`);
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
    if (rule.exclusiveMinimum !== undefined) assert.ok(value > rule.exclusiveMinimum, `${path}: exclusiveMinimum`);
  }
  if (Array.isArray(value)) {
    if (rule.minItems !== undefined) assert.ok(value.length >= rule.minItems, `${path}: minItems`);
    if (rule.items && rule.items !== false) value.forEach((item, index) => validate(item, rule.items, `${path}[${index}]`));
  } else if (value && typeof value === 'object') {
    for (const required of rule.required || []) {
      assert.ok(Object.hasOwn(value, required), `${path}: missing ${required}`);
    }
    if (rule.additionalProperties === false) {
      for (const key of Object.keys(value)) {
        assert.ok(Object.hasOwn(rule.properties || {}, key), `${path}: unknown ${key}`);
      }
    }
    for (const [key, item] of Object.entries(value)) {
      if (rule.properties?.[key]) validate(item, rule.properties[key], `${path}.${key}`);
    }
  }
}

test('JavaScript accepts the canonical ScenarioSpec v1 fixture', () => {
  validate(fixture, schema);
});

test('JavaScript accepts the current economics-v2 ScenarioSpec snapshot', () => {
  validate(economicsV2Fixture, schema);
});

test('JavaScript rejects an unknown major version', () => {
  assert.throws(() => validate({ ...fixture, schema_version: 'scenario-spec-v2' }, schema));
});

test('JavaScript rejects unknown contract fields', () => {
  assert.throws(() => validate({ ...fixture, renderer_internal: {} }, schema));
  assert.throws(() => validate({
    ...fixture,
    economics: { ...fixture.economics, renderer_internal: 1 },
  }, schema));
});
