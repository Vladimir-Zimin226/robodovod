import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/components/ProjectFileIntake.jsx', import.meta.url), 'utf8');

test('file intake requires preview before apply and carries CSRF on mutation', () => {
  assert.match(source, /files\/\$\{mode\}/);
  assert.match(source, /preview\?\.valid/);
  assert.match(source, /X-CSRF-Token/);
  assert.match(source, /Проект изменится только после/);
});

test('file intake accepts only XLSX and CSV and exposes a profile template', () => {
  assert.match(source, /accept="\.xlsx,\.csv"/);
  assert.match(source, /project-file-templates/);
  assert.match(source, /accepted_count/);
  assert.match(source, /error_count/);
});
