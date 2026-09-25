import test from 'node:test';
import assert from 'node:assert/strict';

import { baseNpv, branchAvailability, comparisonRows, groupProjectRuns, reportType } from '../src/reportHistoryModel.js';

const summary = (group, { fleet = 2, type = 'PARTIAL', purchase = null, raas = null } = {}) => ({
  group_run_id: group, fleet, result_type: type,
  branches: { capacity: 'CALCULATED', labour: 'CALCULATED', purchase: purchase == null ? 'NOT_CALCULATED' : 'CALCULATED',
    raas: raas == null ? 'NOT_CALCULATED' : 'CALCULATED', simulation: 'NOT_SAVED' },
  npv: [purchase == null ? null : { acquisition: 'PURCHASE', uncertainty: 'BASE', value: purchase },
    raas == null ? null : { acquisition: 'RAAS', uncertainty: 'BASE', value: raas }].filter(Boolean),
});
const run = (id, group, created, options = {}) => ({ id, project_id: 'project-a', run_kind: 'FULL_ANALYSIS',
  created_at: created, report_summary: summary(group, options) });

test('groups saved versions by their technical source without summing zones', () => {
  const a = run('a', 'capacity-a', '2026-09-25T10:00:00Z', { fleet: 2, purchase: '100.00' });
  const b = run('b', 'capacity-a', '2026-09-26T10:00:00Z', { fleet: 3, purchase: '200.00', type: 'FULL' });
  const c = run('c', 'capacity-b', '2026-09-26T09:00:00Z', { fleet: 7, purchase: '300.00' });
  const groups = groupProjectRuns([a, c, b]);
  assert.deepEqual(groups.map((group) => group.runs.map((item) => item.id)), [['b', 'a'], ['c']]);
  assert.equal(baseNpv(a.report_summary, 'RAAS'), null);
  assert.equal(branchAvailability(a.report_summary, 'raas'), 'Не рассчитано');
  assert.equal(reportType(a), 'Частичный');
  assert.equal(reportType(b), 'Полный');
  const rows = comparisonRows(a, b);
  assert.equal(rows.find((row) => row.label === 'Технический парк').left, 2);
  assert.equal(rows.find((row) => row.label === 'Технический парк').right, 3);
  assert.equal(rows.find((row) => row.label.includes('NPV покупки')).right, '200.00');
  assert.throws(() => comparisonRows(a, c), /одной операции/);
  assert.throws(() => comparisonRows(a, { ...b, project_id: 'project-b' }), /одной операции/);
});

test('technical reports remain visibly partial and unknown money remains unknown', () => {
  const technical = { ...run('t', 'capacity-t', '2026-09-26T12:00:00Z'), run_kind: 'CAPACITY_ANALYSIS' };
  assert.equal(reportType(technical), 'Технический · частичный');
  assert.equal(baseNpv(technical.report_summary, 'PURCHASE'), null);
  assert.equal(reportType({ ...technical, status: 'FAILED' }), 'Ошибка расчёта');
});
