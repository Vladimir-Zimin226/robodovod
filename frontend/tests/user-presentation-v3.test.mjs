import assert from 'node:assert/strict';
import test from 'node:test';
import { decimalDifference, formatDecimal, formatPercent } from '../src/displayNumber.js';
import { humanizePresentation, presentationValue, sourceLabel, statusLabel } from '../src/presentation.js';
import { savedConditions } from '../src/savedConditions.js';

test('display preserves large Decimal precision and distinguishes missing and zero', () => {
  assert.equal(presentationValue('purchase_price_override_gross', '9007199254740993.12'), '9 007 199 254 740 993,12 ₽');
  assert.equal(decimalDifference('9007199254740993.12', '9007199254740993.11'), '0.01');
  assert.equal(decimalDifference('-10.001', '2.22'), '-12.221');
  assert.equal(presentationValue('', null), 'Не указано');
  assert.equal(presentationValue('purchase_price_override_gross', '0'), '0,00 ₽');
  assert.equal(presentationValue('discount_rate', '0.15'), '15 %');
  assert.equal(presentationValue('start_seconds_from_midnight', '32400'), '09:00 · местное время');
  assert.equal(formatDecimal('4.545454545454'), '4,55');
  assert.equal(formatPercent('0.428571428571', 1), '42,9 %');
  assert.equal(statusLabel('UNKNOWN'), 'Не подтверждено');
});

test('saved overview includes active policy and money bases with unchanged source object', () => {
  const input = { purchase_price_override_gross: '2500000', implementation_mode: 'PERCENT',
    implementation_percent: '10', implementation_cost_total_gross: '999', discount_rate: '0.15',
    assumption_evidence: { purchase_price_override_gross: { confirmed: true, source: 'USER',
      rationale: 'Авторское допущение; backend/test_economics.py F08', published_on: '2026-09-29' } },
    staffing_policy: { robots_per_control_post: '5', rotation_factor: '1.5', confirmed: true, source: 'ASSUMPTION' },
    staffing_purchase: { control_mode: 'TRANSFER', technician_mode: 'HIRE' },
    work_share: { fraction: '0.8', residual_operations: 'Проверка груза', confirmed: true },
  };
  const result = { monetary_input_basis: { unit_price_gross_rub: '2500000', implementation: { amount_gross_rub: '2750000' } } };
  const before = JSON.stringify({ input, result });
  const rows = savedConditions(input, result).flatMap((group) => group.rows);
  assert.ok(rows.some((row) => row.value === '2 500 000,00 ₽' && row.confirmed));
  assert.ok(rows.some((row) => row.value === '80 %'));
  assert.ok(rows.some((row) => row.value === 'Перевод сотрудника'));
  assert.ok(rows.some((row) => row.value === '2 750 000,00 ₽'));
  assert.ok(!rows.some((row) => row.value.includes('999')));
  assert.equal(JSON.stringify({ input, result }), before);
  assert.doesNotMatch(JSON.stringify(rows), /test_economics|F08|rationale/);
  assert.equal(sourceLabel({ source: 'ASSUMPTION' }), 'Сценарное допущение');
  assert.doesNotMatch(humanizePresentation('C14 F08 R01 K02 UNKNOWN sha256:' + 'f'.repeat(64) + ' backend/test_cost.py'), /C14|F08|R01|K02|UNKNOWN|sha256|test_cost/);
});
