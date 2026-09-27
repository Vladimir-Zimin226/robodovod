import assert from 'node:assert/strict';
import test from 'node:test';
import { catalogDiagnostics, recommendedCandidates } from '../src/candidateRecommendation.js';

test('preview leader skips blocked catalog positions and keeps unverified alternatives', () => {
  const catalog = [
    { position_id: 'blocked', selection: { status: 'EXCLUDED' } },
    { position_id: 'first', selection: { status: 'REQUIRES_CHECK', calculation_compatible: true } },
    { position_id: 'second', selection: { status: 'INCLUDED', calculation_compatible: true } },
  ];
  const comparison = { catalog_position_count: 223, profile_position_count: 3, candidates: [
    { position_id: 'blocked', technical_score: '99', status: 'TECHNICAL_ONLY' },
    { position_id: 'outside-object', technical_score: '100', status: 'TECHNICAL_ONLY' },
    { position_id: 'first', technical_score: '71', status: 'TECHNICAL_ONLY' },
    { position_id: 'second', technical_score: '65', status: 'TECHNICAL_ONLY' },
  ] };
  assert.deepEqual(recommendedCandidates(comparison, catalog).map((item) => item.position_id), ['first', 'second']);
  assert.deepEqual(catalogDiagnostics(catalog, comparison), {
    active: 223, process: 3, profile: 3, excluded: 1, check: 1, ready: 2,
  });
});
