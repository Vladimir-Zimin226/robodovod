import assert from 'node:assert/strict';
import test from 'node:test';

import { PRESENTATION_VERSION, fieldPresentation, humanizePresentation, savedCalculationLabel,
  sectionLabel, statusLabel, subsystemLabel } from '../src/presentation.js';

test('one presentation glossary gives readable labels and concrete next steps', () => {
  assert.equal(PRESENTATION_VERSION, 'readable-presentation-v2');
  assert.equal(subsystemLabel('C11'), 'расчёт потребного парка');
  assert.equal(sectionLabel('CashFlow'), 'Денежные потоки');
  assert.equal(statusLabel('NEEDS_VALIDATION'), 'требуется проверка условий объекта');
  const field = fieldPresentation('raas_vendor_scope_confirmed');
  assert.equal(field.label, 'состав тарифа аренды');
  assert.match(field.action, /Подтвердите состав/);
  assert.doesNotMatch(humanizePresentation('C05 NEEDS_VALIDATION и C23'), /C\d{2}|NEEDS_VALIDATION/);
  assert.equal(savedCalculationLabel('2026-09-25T23:45:00Z'), 'Сохранённый расчёт от 25 сентября 2026 г.');
});
