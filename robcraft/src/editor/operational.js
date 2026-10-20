import { circleIntersectsSolid, solidExtents } from './collisions.js';
import { triangulateRoom } from './room-polygon.js';
import { planGridPath } from '../navigation.js';

export function operationalRolesFor(item) {
  const kind = item.kind || item.editorKind;
  if (['charger', 'charging_dock'].includes(kind)) return ['CHARGE'];
  if (['station', 'conveyor', 'nurse_desk', 'cargo', 'pallet_stack', 'baggage_cart', 'hospital_cart', 'painted_floor_marker'].includes(kind)) return ['WORK', 'DROPOFF'];
  return [];
}

function approachPoint(object, scene, radius) {
  const center = [object.position[0], object.position[2]];
  if (object.solid === false) return center;
  const extent = solidExtents(object);
  const offset = radius + .25;
  const candidates = [
    [center[0], center[1] + extent.z + offset],
    [center[0], center[1] - extent.z - offset],
    [center[0] + extent.x + offset, center[1]],
    [center[0] - extent.x - offset, center[1]]
  ];
  return candidates.find(([x, z]) => Math.abs(x) <= scene.config.width / 2 - radius && Math.abs(z) <= scene.config.depth / 2 - radius &&
    !scene.solids.some(solid => circleIntersectsSolid(x, z, radius, solid))) || center;
}

export function operationalAnchors(scene, radius = .6) {
  const objects = scene.staticObjects.filter(item => item.operational_role);
  const anchors = objects.map(object => ({
    id: object.id, role: object.operational_role, label: object.meta?.label || object.kind,
    position: approachPoint(object, scene, radius), source: 'object'
  }));
  for (const zone of scene.editorZones || []) {
    if (zone.operational_role !== 'WORK') continue;
    const triangle = triangulateRoom(zone.points)?.[0];
    if (!triangle) continue;
    anchors.push({ id: zone.id, role: 'WORK', label: zone.name, source: 'zone',
      position: [0, 1].map(axis => triangle.reduce((sum, index) => sum + zone.points[index][axis], 0) / 3) });
  }
  return anchors;
}

export function planOperationalPath(scene, selection, radius = .6) {
  const anchors = operationalAnchors(scene, radius);
  const get = (id, role) => anchors.find(anchor => anchor.id === id && anchor.role === role);
  const charge = get(selection.chargeId, 'CHARGE');
  const work = get(selection.workId, 'WORK');
  const dropoff = selection.dropoffId ? get(selection.dropoffId, 'DROPOFF') : null;
  if (!charge) return { ok: false, reason: 'Нет доступной точки CHARGE.' };
  if (!work) return { ok: false, reason: 'Нет доступной точки WORK.' };
  if (selection.dropoffId && !dropoff) return { ok: false, reason: 'Точка DROPOFF удалена или изменила роль.' };
  const visits = [charge, work, ...(dropoff ? [dropoff] : []), charge];
  const bounds = { minX: -scene.config.width / 2 + radius, maxX: scene.config.width / 2 - radius,
    minZ: -scene.config.depth / 2 + radius, maxZ: scene.config.depth / 2 - radius };
  const points = [[...charge.position]];
  const waypointIndices = [0];
  for (let index = 0; index < visits.length - 1; index += 1) {
    const start = visits[index], target = visits[index + 1];
    if (start.position.some((value, axis) => value < (axis ? bounds.minZ : bounds.minX) || value > (axis ? bounds.maxZ : bounds.maxX)) ||
        target.position.some((value, axis) => value < (axis ? bounds.minZ : bounds.minX) || value > (axis ? bounds.maxZ : bounds.maxX)))
      return { ok: false, reason: `Точка ${start.label} или ${target.label} слишком близко к границе площадки.` };
    if (scene.solids.some(solid => circleIntersectsSolid(start.position[0], start.position[1], radius, solid)) ||
        scene.solids.some(solid => circleIntersectsSolid(target.position[0], target.position[1], radius, solid)))
      return { ok: false, reason: `Точка ${start.label} или ${target.label} перекрыта препятствием.` };
    const leg = planGridPath(start.position, target.position, { solids: scene.solids, radius, bounds });
    if (!leg) return { ok: false, reason: `Нет прохода: ${start.role} → ${target.role}.` };
    points.push(...leg);
    waypointIndices.push(points.length - 1);
  }
  const distance = points.slice(1).reduce((sum, point, index) => sum + Math.hypot(point[0] - points[index][0], point[1] - points[index][1]), 0);
  return { ok: true, points, distance, visits: visits.map(anchor => anchor.id), waypointIndices };
}

export const ASSIGNABLE_ROBOTS = Object.freeze({
  pallet_amr: 'pallet-amr', forklift_robot: 'forklift', airport_tug: 'baggage-tug', indoor_delivery_robot: 'medical-cart'
});
