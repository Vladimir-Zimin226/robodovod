import warehouse from '../../data/scenes/warehouse.scene.json' with { type: 'json' };
import airport from '../../data/scenes/airport.scene.json' with { type: 'json' };
import clinic from '../../data/scenes/clinic.scene.json' with { type: 'json' };

const SCENES = Object.freeze({ warehouse, airport, clinic });

export function sceneForKind(kind) {
  return SCENES[kind === 'retail' || kind === 'WAREHOUSE' ? 'warehouse'
    : kind === 'AIRPORT' ? 'airport' : kind === 'CLINIC' ? 'clinic' : kind] || null;
}

function finite(value, label) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError(`${label} must be finite`);
}

export function validateScene(scene) {
  if (scene?.schema_version !== 'scene-model-v1' || scene.units !== 'm'
      || scene.coordinate_system !== 'x-east_y-north_z-up' || !Number.isInteger(scene.revision)) {
    throw new TypeError('Unsupported SceneModel coordinate contract');
  }
  const { width_m: width, length_m: length } = scene.bounds;
  finite(width, 'width'); finite(length, 'length');
  if (width <= 0 || length <= 0) throw new RangeError('SceneModel bounds must be positive');
  const inside = ([x, y], label) => {
    finite(x, `${label}.x`); finite(y, `${label}.y`);
    if (x < 0 || x > width || y < 0 || y > length) throw new RangeError(`${label} outside scene bounds`);
  };
  const ids = new Set();
  for (const object of scene.objects) {
    if (ids.has(object.instance_id)) throw new TypeError(`Duplicate instance ${object.instance_id}`);
    ids.add(object.instance_id);
    inside(object.position_m, object.instance_id);
    const [dx, dy] = object.footprint_m;
    finite(dx, 'footprint width'); finite(dy, 'footprint length');
    if (dx <= 0 || dy <= 0) throw new RangeError('Nonpositive footprint');
    const [x, y] = object.position_m;
    inside([x - dx / 2, y - dy / 2], object.instance_id);
    inside([x + dx / 2, y + dy / 2], object.instance_id);
    finite(object.visual_height_m, 'visual height');
  }
  for (const zone of scene.zones) {
    if (ids.has(zone.zone_id)) throw new TypeError(`Duplicate zone ${zone.zone_id}`);
    ids.add(zone.zone_id);
    for (const point of zone.polygon_xy_m) inside(point, zone.zone_id);
  }
  for (const route of scene.routes) for (const point of route.points_xy_m) inside(point, route.route_id);
  return scene;
}

// SceneModel uses X/Y on the floor and Z up. glTF/Three.js uses Y up.
// This adapter is the only axis conversion; renderers never swap axes again.
export function worldToGltf([x, y, z]) { return [x, z, -y]; }
export function gltfToWorld([x, y, z]) { return [x, -z, y]; }

export function topProjection(scene, width = 600, padding = 20) {
  const scale = (width - 2 * padding) / scene.bounds.width_m;
  return {
    width, height: scene.bounds.length_m * scale + 2 * padding, scale,
    point: ([x, y]) => [padding + x * scale, padding + (scene.bounds.length_m - y) * scale],
  };
}

export function isoProjection(scene, width = 600, padding = 20) {
  const cosine = Math.cos(Math.PI / 6);
  const sine = Math.sin(Math.PI / 6);
  const scale = (width - 2 * padding) / ((scene.bounds.width_m + scene.bounds.length_m) * cosine);
  return {
    width, height: (scene.bounds.width_m + scene.bounds.length_m) * sine * scale
      + scene.bounds.height_m * scale + 2 * padding, scale,
    point: (worldPoint) => {
      const [x, up, depth] = worldToGltf(worldPoint);
      return [padding + (x + depth + scene.bounds.length_m) * cosine * scale,
        padding + scene.bounds.height_m * scale + (x - depth) * sine * scale - up * scale];
    },
  };
}

export function footprintCorners(object, z = 0) {
  const [x, y] = object.position_m;
  const [dx, dy] = object.footprint_m;
  return [[x - dx / 2, y - dy / 2, z], [x + dx / 2, y - dy / 2, z],
    [x + dx / 2, y + dy / 2, z], [x - dx / 2, y + dy / 2, z]];
}

export function buildSceneViews(scene) {
  validateScene(scene);
  return {
    top: { objects: scene.objects.map((object) => ({ id: object.instance_id, corners: footprintCorners(object) })),
      zones: scene.zones.map((zone) => ({ id: zone.zone_id, polygon: zone.polygon_xy_m })),
      routes: scene.routes.map((route) => ({ id: route.route_id, points: route.points_xy_m })) },
    iso: { objects: scene.objects.map((object) => ({ id: object.instance_id,
      base: footprintCorners(object), top: footprintCorners(object, object.visual_height_m) })),
    zones: scene.zones.map((zone) => ({ id: zone.zone_id, polygon: zone.polygon_xy_m })),
    routes: scene.routes.map((route) => ({ id: route.route_id, points: route.points_xy_m })) },
  };
}

export function sceneWithSimulation(scene, request, simulation) {
  if (!request || !simulation) return scene;
  const moved = scene.zones.map((zone) => {
    const target = zone.zone_id === 'pickup' ? request.pickup_xy_m
      : zone.zone_id === 'delivery' ? request.dropoff_xy_m : null;
    if (!target) return zone;
    const delta = [target[0] - zone.center_xy_m[0], target[1] - zone.center_xy_m[1]];
    return { ...zone, center_xy_m: target,
      polygon_xy_m: zone.polygon_xy_m.map(([x, y]) => [x + delta[0], y + delta[1]]) };
  });
  const added = (request.extra_obstacles || []).map((obstacle, index) => ({
    instance_id: `user-block-${index + 1}`, asset_id: 'user_barrier',
    position_m: [obstacle.x, obstacle.y, 0], footprint_m: [obstacle.width, obstacle.height],
    visual_height_m: 1.5, blocks_navigation: true, source: 'SCENARIO_ASSUMPTION',
  }));
  const lane = request.shared_lane;
  if (lane) {
    moved.push({ zone_id: 'user-shared-lane', kind: 'SHARED_LANE', name: 'Общий узкий участок',
      center_xy_m: [lane.x, lane.y], source: 'SCENARIO_ASSUMPTION',
      polygon_xy_m: [[lane.x - lane.width / 2, lane.y - lane.height / 2],
        [lane.x + lane.width / 2, lane.y - lane.height / 2],
        [lane.x + lane.width / 2, lane.y + lane.height / 2],
        [lane.x - lane.width / 2, lane.y + lane.height / 2]] });
  }
  const routes = simulation.routes.map((route) => ({ route_id: `sim-${route.kind.toLowerCase()}`,
    points_xy_m: route.points_xy_m, source: 'SCENARIO_ASSUMPTION', status: simulation.status }));
  return validateScene({ ...scene, objects: [...scene.objects, ...added], zones: moved, routes });
}
