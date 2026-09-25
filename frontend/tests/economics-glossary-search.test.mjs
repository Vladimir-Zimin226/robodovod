import test from 'node:test';
import assert from 'node:assert/strict';
import glossary from '../src/economicsGlossary.json' with { type: 'json' };
import { searchEconomicsEntries } from '../src/economicsGlossarySearch.js';

test('finds Russian term, synonym and notation', () => {
  for (const [query, id] of [
    ['окупаемость', 'payback'], ['NPV', 'npv'], ['цена владения', 'tco'],
    ['ЧПС', 'npv'], ['ёМКОСТЬ', null], ['раас', 'raas'],
  ]) {
    const found = searchEconomicsEntries(glossary.entries, query).map((item) => item.id);
    if (id) assert.ok(found.includes(id), `${query}: ${found.join(', ')}`);
    else assert.equal(found.length, 0);
  }
});

test('every term exposes a formula, units, inputs, example and provenance', () => {
  assert.equal(glossary.entries.length, 13);
  for (const entry of glossary.entries) {
    for (const field of ['formula', 'units', 'example', 'applicability', 'source', 'section', 'example_source']) {
      assert.ok(entry[field], `${entry.id}.${field}`);
    }
    assert.ok(entry.inputs.length > 0, `${entry.id}.inputs`);
    assert.ok(entry.formula_ids.length > 0, `${entry.id}.formula_ids`);
  }
});
