import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { basisSourceLabel, calculationLabel, readableBasis, sourceLabel } from '../src/roleSourcePresentation.js';

const rows = JSON.parse(readFileSync(new URL('../src/roleWorkScenarioData.json', import.meta.url), 'utf8')).records;

test('all role work explanations hide workbook cells and internal row identifiers', () => {
  for (const row of rows) {
    for (const key of ['work_basis', 'salary_source_ref', 'headcount_source_ref']) {
      const label = readableBasis(row[key]);
      assert.ok(label.length > 0, `${row.role_code}: ${key}`);
      assert.doesNotMatch(label, /(?:RW-[A-Z0-9_-]+|![A-ZА-Я]*C\d+|\bC\d+\b|ASSUMPTION_V\d+)/i);
    }
  }
});

test('number sources and calculation states use plain language', () => {
  assert.match(sourceLabel('CATALOG_VERIFIED'), /каталога/i);
  assert.match(sourceLabel('USER_ASSUMPTION'), /ваши/i);
  assert.match(sourceLabel('FORMULA'), /формуле/i);
  assert.match(sourceLabel('Склад!C31'), /допущение/i);
  assert.match(basisSourceLabel('RW-WH-FORKLIFT-01: Склад!C18 = 2000'), /допущение/i);
  assert.match(basisSourceLabel('Замер на объекте 20 октября'), /ваши/i);
  assert.doesNotMatch(calculationLabel('REFERENCE_ONLY'), /C11|ASSUMPTION|REFERENCE_ONLY/);
});
