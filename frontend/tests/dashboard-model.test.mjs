import test from 'node:test';
import assert from 'node:assert/strict';

import { getDashboardModel, getRecommended, getScenario } from '../src/dashboardModel.js';

const acceptable = {
  robot_id: 'recommended',
  is_best: true,
  economic_status: 'ACCEPTABLE',
  readiness_score: 88,
  quantity: 2,
  scenarios: [{ scenario: 'base', quantity: 2, capex: 10, payback_years: 3 }],
};

const rejectedEconomics = {
  robot_id: 'first-but-not-best',
  is_best: false,
  economic_status: 'NOT_ACCEPTABLE',
  readiness_score: 95,
  quantity: 1,
  scenarios: [{ scenario: 'base', quantity: 1, capex: 5, payback_years: 99 }],
};

test('recommended variant is selected strictly by is_best, not array position', () => {
  assert.equal(getRecommended([rejectedEconomics, acceptable]), acceptable);
  assert.equal(getScenario(acceptable, 'base').capex, 10);
});

test('NO_ACCEPTABLE_ECONOMICS never creates a dashboard recommendation', () => {
  const model = getDashboardModel({
    recommendations: [rejectedEconomics],
    warnings: ['Экономика всех вариантов неприемлема'],
    data_quality: { completeness_pct: 90 },
    scenario_spec: { fleet: [], economics: { status: 'NO_ACCEPTABLE_ECONOMICS' } },
  }, { staff_headcount: 4 }, 'base');

  assert.equal(model.recommended, null);
  assert.equal(model.economics, null);
  assert.equal(model.hasAcceptableRecommendation, false);
  assert.equal(model.fleetSize, 0);
  assert.match(model.warning, /неприемлема/);
});
