import assert from 'node:assert/strict';
import test from 'node:test';

import { buildSceneViews, footprintCorners, gltfToWorld, isoProjection,
  sceneForKind, sceneWithSimulation, topProjection, validateScene, worldToGltf } from '../src/sceneModel.js';

for (const [kind, expected] of [['retail', [60, 40, 13]], ['airport', [76, 48, 10]], ['clinic', [45, 28, 17]]]) {
  test(`${kind}: one scene supplies both projections and obstacle footprints`, () => {
    const scene = validateScene(sceneForKind(kind));
    assert.deepEqual([scene.bounds.width_m, scene.bounds.length_m,
      scene.objects.filter((object) => object.blocks_navigation).length], expected);
    assert(scene.objects.some((object) => object.visual_only && !object.blocks_navigation));
    assert.equal(scene.fidelity, 'DEMO_ASSUMPTION');
    const { top, iso } = buildSceneViews(scene);
    assert.deepEqual(top.objects.map(({ id }) => id), iso.objects.map(({ id }) => id));
    assert.deepEqual(top.zones, iso.zones);
    assert.deepEqual(top.routes, iso.routes);
    const plan = topProjection(scene);
    const perspective = isoProjection(scene);
    assert(Math.abs(plan.point([0, 0])[1] - plan.point([0, 5])[1] - 5 * plan.scale) < 1e-9);
    for (const object of scene.objects) {
      const source = footprintCorners(object);
      const inTop = top.objects.find(({ id }) => id === object.instance_id);
      const inIso = iso.objects.find(({ id }) => id === object.instance_id);
      assert.deepEqual(inTop.corners, source);
      assert.deepEqual(inIso.base, source);
      assert.deepEqual(inIso.top.map(([x, y]) => [x, y]), source.map(([x, y]) => [x, y]));
      assert(Math.abs(Math.abs((source[1][0] - source[0][0]) * (source[2][1] - source[1][1]))
        - object.footprint_m[0] * object.footprint_m[1]) < 1e-9);
      for (const point of source) {
        assert.deepEqual(gltfToWorld(worldToGltf(point)), point);
        assert(plan.point(point).every(Number.isFinite));
        assert(perspective.point(point).every(Number.isFinite));
      }
    }
  });
}

test('invalid units, duplicate IDs and out-of-bounds footprints fail closed', () => {
  const scene = sceneForKind('retail');
  assert.throws(() => validateScene({ ...scene, units: 'cm' }), /coordinate contract/);
  assert.throws(() => validateScene({ ...scene, objects: [scene.objects[0], scene.objects[0]] }), /Duplicate/);
  assert.throws(() => validateScene({ ...scene, objects: [{ ...scene.objects[0], position_m: [0, 0, 0] }] }), /outside/);
});

test('simulation route, moved zone and barrier update both views from one overlay', () => {
  const source = sceneForKind('retail');
  const request = { pickup_xy_m: [11, 31], dropoff_xy_m: [54, 34],
    extra_obstacles: [{ x: 25, y: 34, width: 2, height: 2 }],
    shared_lane: { x: 30, y: 34, width: 8, height: 2 } };
  const simulation = { status: 'MODELED', routes: [{ kind: 'LOADED', points_xy_m: [[11, 31], [20, 31], [54, 34]] },
    { kind: 'EMPTY', points_xy_m: [[54, 34], [11, 31]] }] };
  const model = sceneWithSimulation(source, request, simulation);
  const { top, iso } = buildSceneViews(model);
  assert.deepEqual(model.zones.find((zone) => zone.zone_id === 'pickup').center_xy_m, [11, 31]);
  assert(top.objects.some((object) => object.id === 'user-block-1'));
  assert.deepEqual(top.objects.map(({ id }) => id), iso.objects.map(({ id }) => id));
  assert.deepEqual(top.zones, iso.zones);
  assert(top.zones.some(({ id }) => id === 'user-shared-lane'));
  assert.deepEqual(top.routes, iso.routes);
  assert.deepEqual(top.routes.map(({ id }) => id), ['sim-loaded', 'sim-empty']);
  assert.equal(source.objects.length + 1, model.objects.length);
});
