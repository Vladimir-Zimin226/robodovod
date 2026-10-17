import test from 'node:test';
import assert from 'node:assert/strict';
import { emptyFacilityLayout, estimateFacilityRoute, exampleFacilityLayout, layoutFingerprint, parseFacilityLayoutDraft } from '../src/facilityLayout.js';
import { createDraft, loadConfirmedTypicalObjectDraft, serializeDraft, updateFacilityPlan, updateProcess, validateDraft } from '../src/processRoleIntakeV2.js';
import { savedLayoutPayload } from '../src/facilityLayoutEvidence.js';

test('an authored obstacle creates a longer passable route and a wall can block it', () => {
  const example = exampleFacilityLayout();
  const withObstacle = estimateFacilityRoute(example);
  assert.equal(withObstacle.status, 'READY');
  assert.ok(withObstacle.length_m > withObstacle.straight_m);
  const noObstacle = estimateFacilityRoute({ ...example, items: example.items.filter((item) => item.id !== 'island') });
  assert.equal(noObstacle.status, 'READY');
  assert.ok(withObstacle.length_m > noObstacle.length_m);
  const blocked = estimateFacilityRoute({ ...emptyFacilityLayout(), items: [
    { kind: 'pickup', x: 5, y: 5 }, { kind: 'dropoff', x: 55, y: 5 },
    { kind: 'no_go', x: 29, y: 0, width_m: 2, depth_m: 36 },
  ] });
  assert.equal(blocked.status, 'BLOCKED');
});

test('applied route enters the existing server intake contract with explicit origin', () => {
  const layout = exampleFacilityLayout();
  const route = estimateFacilityRoute(layout);
  let draft = updateFacilityPlan(loadConfirmedTypicalObjectDraft('retail'), layout);
  draft = updateProcess(draft, 'warehouse_receiving_shipping', {
    distance: String(route.length_m), distanceFromPlan: layoutFingerprint(layout),
  });
  const serialized = serializeDraft(draft);
  const transport = serialized.processes.find((item) => item.process_code === 'warehouse_receiving_shipping');
  assert.equal(transport.route_distance.value, String(route.length_m));
  assert.match(transport.route_distance.provenance.raw_text, /предварительную оценку по нарисованной планировке/);
  draft = updateFacilityPlan(draft, { ...layout, items: layout.items.filter((item) => item.id !== 'island') });
  assert.ok(validateDraft(draft).some((issue) => issue.code === 'ROUTE_REQUIRED'));
});

test('editing a plan invalidates a route distance previously applied to intake', () => {
  const layout = exampleFacilityLayout();
  const route = estimateFacilityRoute(layout);
  let draft = createDraft('retail');
  draft = updateFacilityPlan(draft, layout);
  draft = updateProcess(draft, 'warehouse_receiving_shipping', {
    distance: String(route.length_m), distanceFromPlan: layoutFingerprint(layout),
  });
  const previousRevision = draft.inputRevision;
  draft = updateFacilityPlan(draft, { ...layout, items: [...layout.items,
    { id: 'new-rack', kind: 'rack', x: 42, y: 10, provenance: 'DRAWN' }] });
  assert.notEqual(draft.inputRevision, previousRevision);
  const process = draft.processes.find((item) => item.code === 'warehouse_receiving_shipping');
  assert.equal(process.distance, '');
  assert.equal(process.distanceFromPlan, null);
  draft = updateProcess(draft, process.processId, { distance: '60' });
  assert.equal(draft.processes.find((item) => item.processId === process.processId).distanceFromPlan, null);
});

test('a downloaded plan can be reopened without trusting embedded image data or invalid coordinates', () => {
  const sample = exampleFacilityLayout();
  const imported = parseFacilityLayoutDraft(JSON.stringify({ ...sample, imageData: 'data:text/html,unsafe' }));
  assert.equal(imported.imageData, null);
  assert.equal(estimateFacilityRoute(imported).length_m, estimateFacilityRoute(sample).length_m);
  assert.throws(() => parseFacilityLayoutDraft(JSON.stringify({ ...sample, items: [
    { kind: 'rack', x: 71, y: 1, width_m: 7, depth_m: 2 },
  ] })), /за пределы/);
});

test('the run evidence keeps authored geometry and excludes the image underlay', () => {
  const layout = { ...exampleFacilityLayout(), imageData: 'data:image/png;base64,example' };
  const payload = savedLayoutPayload({ facilityPlan: layout, appliedDistanceM: 52,
    processId: 'zone.main.transport' });
  assert.equal(payload.applied_distance_m, '52');
  assert.equal(payload.layout.image_not_embedded, true);
  assert.equal(Object.hasOwn(payload.layout, 'imageData'), false);
  assert.equal(payload.layout.items.length, layout.items.length);
  assert.equal(payload.layout.items.find((item) => item.id === 'island').width_m, 4);
});
