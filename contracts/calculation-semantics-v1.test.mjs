import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

function load(relative) {
  return JSON.parse(readFileSync(new URL(relative, import.meta.url), 'utf8'));
}

function dereference(rule, schema) {
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

function validate(value, sourceRule, schema, path = '$') {
  const rule = dereference(sourceRule, schema);
  for (const keyword of ['oneOf', 'anyOf']) {
    if (rule[keyword]) {
      const valid = rule[keyword].filter((candidate) => {
        try { validate(value, candidate, schema, path); return true; } catch { return false; }
      });
      if (keyword === 'oneOf') assert.equal(valid.length, 1, `${path}: exactly one oneOf`);
      else assert.ok(valid.length >= 1, `${path}: anyOf`);
      return;
    }
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
    if (rule.items) value.forEach((item, index) => validate(item, rule.items, schema, `${path}[${index}]`));
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
      if (rule.properties?.[key]) validate(item, rule.properties[key], schema, `${path}.${key}`);
    }
  }
}

const cases = [
  ['./calculation-semantics-fixture-v1.schema.json', './fixtures/calculation-semantics-v1.complete.json'],
  ['./calculation-trace-v1.schema.json', './fixtures/calculation-trace-v1.blocked-missing-speed.json'],
  ['./calculation-partial-result-v1.schema.json', './fixtures/calculation-partial-result-v1.capacity-only.json'],
  ['./calculation-decision-fixtures-v1.schema.json', './fixtures/calculation-decision-fixtures-v1.json'],
  ['./calculation-semantics-manifest-v1.schema.json', './calculation-semantics-manifest-v1.json'],
  ['./capacity-analysis-error-v1.schema.json', './fixtures/capacity-analysis-error-v1.blocked.json'],
];

for (const [schemaPath, fixturePath] of cases) {
  test(`JavaScript validates ${fixturePath}`, () => {
    const schema = load(schemaPath);
    validate(load(fixturePath), schema, schema);
  });
}

test('JavaScript rejects unknown versions and extra fields', () => {
  const schema = load('./calculation-trace-v1.schema.json');
  const fixture = load('./fixtures/calculation-trace-v1.blocked-missing-speed.json');
  assert.throws(() => validate({ ...fixture, extra: true }, schema, schema));
  const changed = structuredClone(fixture);
  changed.envelope.schema_version = 'calculation-trace-v2';
  assert.throws(() => validate(changed, schema, schema));
});
