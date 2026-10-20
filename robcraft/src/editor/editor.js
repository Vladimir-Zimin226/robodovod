import { canPlaceSolid, solidExtents } from './collisions.js';
import { applyScenePatch, compatibleRobotTypes, createScenePatch, listEditableEntities, SceneHistory } from './scene-patch.js';
import { validZonePolygon } from './map-view.js';
import { validRoomPolygon } from './room-polygon.js';
import { ASSIGNABLE_ROBOTS, operationalRolesFor, planOperationalPath } from './operational.js';
import { robotProfile } from '../world/robot-catalog.js';
import { validateEconomicsInputs } from './live-economics.js';

export const BUILD_CATALOG = Object.freeze([
  { kind: 'wall', label: 'Стена', category: 'Конструкции', scale: [4, 3, .3], color: [.73, .78, .75] },
  { kind: 'rack', label: 'Стеллаж', category: 'Конструкции', scale: [2.5, 4.7, 1.25], color: [.18, .25, .25] },
  { kind: 'cargo', label: 'Паллета / груз', category: 'Мебель/Оборудование', scale: [1.2, .8, 1], color: [.64, .42, .20] },
  { kind: 'station', label: 'Рабочая станция', category: 'Мебель/Оборудование', scale: [3, 1, 1.8], color: [.95, .72, .10] },
  { kind: 'charger', label: 'Зарядная позиция', category: 'Зоны/Маршруты', scale: [1, .16, 1.2], color: [.12, .75, .48], solid: false },
  { kind: 'fence', label: 'Ограждение', category: 'Конструкции', scale: [3, 1.2, .16], color: [.92, .48, .12] },
  { kind: 'decor', label: 'Декоративный блок', category: 'Декор', scale: [1, 1, 1], color: [.30, .55, .48] },
  { kind: 'pallet_rack', label: 'Паллетный стеллаж', type: 'rack', category: 'Конструкции', scale: [2.5, 4.7, 1.25], color: [.18, .25, .25] },
  { kind: 'pallet_stack', label: 'Паллеты', type: 'cargo', category: 'Мебель/Оборудование', scale: [1.2, .8, 1], color: [.64, .42, .20] },
  { kind: 'charging_dock', label: 'Зарядная станция', type: 'charger', category: 'Зоны/Маршруты', scale: [1.2, .6, 1.2], color: [.12, .75, .48] },
  { kind: 'conveyor', label: 'Конвейер', type: 'station', category: 'Мебель/Оборудование', scale: [3, 1, 1], color: [.48, .58, .62] },
  { kind: 'baggage_cart', label: 'Багажная тележка', type: 'cargo', category: 'Мебель/Оборудование', scale: [1.8, 1.1, 1], color: [.35, .62, .72] },
  { kind: 'hospital_bed', label: 'Больничная кровать', type: 'bed', category: 'Мебель/Оборудование', scale: [2, .9, 1], color: [.8, .9, .9] },
  { kind: 'hospital_cart', label: 'Медицинская тележка', type: 'cargo', category: 'Мебель/Оборудование', scale: [1, 1, .65], color: [.8, .9, .9] },
  { kind: 'nurse_desk', label: 'Стойка медсестры', type: 'station', category: 'Мебель/Оборудование', scale: [2, 1, .8], color: [.8, .9, .9] },
  { kind: 'pallet_amr', label: 'Паллетный AMR', type: 'decor', category: 'Роботы', scale: [1.2, .7, 1], color: [.15, .7, .5] },
  { kind: 'forklift_robot', label: 'Робот-погрузчик', type: 'decor', category: 'Роботы', scale: [2, 2, 1.2], color: [.9, .6, .15] },
  { kind: 'airport_tug', label: 'Аэропортовый тягач', type: 'decor', category: 'Роботы', scale: [2, 1.2, 1.2], color: [.3, .6, .8] },
  { kind: 'indoor_delivery_robot', label: 'Робот доставки', type: 'decor', category: 'Роботы', scale: [.8, 1, .7], color: [.2, .8, .7] },
  { kind: 'worker', label: 'Сотрудник', type: 'decor', category: 'Декор', scale: [.5, 1.8, .5], color: [.7, .7, .8] },
  { kind: 'safety_barrier', label: 'Барьер', type: 'fence', category: 'Конструкции', scale: [2, 1, .2], color: [.9, .5, .2] },
  { kind: 'door_frame', label: 'Дверной проём', type: 'decor', category: 'Конструкции', scale: [2, 2.5, .2], color: [.6, .7, .7] },
  { kind: 'clinic_door', label: 'Дверь клиники', type: 'wall', category: 'Конструкции', scale: [1.2, 2.2, .2], color: [.7, .8, .8] },
  { kind: 'traffic_cone', label: 'Конус', type: 'decor', category: 'Декор', scale: [.45, .7, .45], color: [1, .4, .1] },
  { kind: 'warehouse_column', label: 'Колонна склада', type: 'wall', category: 'Конструкции', scale: [.6, 4, .6], color: [.6, .7, .7] },
  { kind: 'clinic_wall_module', label: 'Стена клиники', type: 'wall', category: 'Конструкции', scale: [3, 2.7, .2], color: [.8, .9, .9] },
  { kind: 'aircraft_marker', label: 'Маркер самолёта', type: 'decor', category: 'Декор', scale: [1, .03, 1], color: [.6, .8, 1], solid: false },
  { kind: 'painted_floor_marker', label: 'Маркер пола', type: 'decor', category: 'Зоны/Маршруты', scale: [1, .03, 1], color: [.8, .9, .2], solid: false }
]);

const clone = value => JSON.parse(JSON.stringify(value));
const snap = (value, step, enabled) => enabled ? Math.round(value / step) * step : value;

export class SceneEditorModel {
  constructor(baseScene, patch = createScenePatch(baseScene.config), historyLimit = 20) {
    this.baseScene = clone(baseScene);
    this.history = new SceneHistory(patch, historyLimit);
    this.selectedId = null;
    this.scene = applyScenePatch(this.baseScene, this.history.present);
  }

  refresh() { this.scene = applyScenePatch(this.baseScene, this.history.present); return this.scene; }
  entities() { return listEditableEntities(this.scene); }
  entity(id = this.selectedId) { return this.entities().find(item => item.id === id) || null; }
  select(id) { this.selectedId = id; return this.entity(); }

  update(id, values) {
    const entity = this.entity(id);
    if (!entity) return false;
    if (this.roomForPart(id)) return false;
    const next = { position: [...entity.position], scale: [...entity.scale], yaw: entity.yaw, ...clone(values) };
    const collider = { position: next.position, scale: next.scale, yaw: next.yaw, editorId: id };
    if (!canPlaceSolid(collider, this.scene.solids, id)) return false;
    this.history.mutate(patch => {
      const created = patch.created.find(item => item.id === id);
      if (created) Object.assign(created, next);
      else patch.objects[id] = next;
    });
    this.refresh();
    return true;
  }

  move(id, delta, options = {}) {
    const entity = this.entity(id); if (!entity) return false;
    const step = options.gridStep || .5; const grid = options.grid !== false;
    return this.update(id, { position: entity.position.map((value, axis) => snap(value + (delta[axis] || 0), step, grid)) });
  }
  rotate(id, angle = Math.PI / 2) { const entity = this.entity(id); return entity ? this.update(id, { yaw: entity.yaw + angle }) : false; }
  resize(id, delta, axis = 0, options = {}) {
    const entity = this.entity(id); if (!entity) return false;
    const scale = [...entity.scale]; scale[axis] = Math.max(.1, snap(scale[axis] + delta, options.gridStep || .5, options.grid !== false));
    return this.update(id, { scale });
  }

  create(kind, position, options = {}) {
    const preset = BUILD_CATALOG.find(item => item.kind === kind); if (!preset) return null;
    const instanceId = crypto.randomUUID();
    const id = `user:${kind}:${instanceId}`;
    const object = { id, instance_id: instanceId, kind, editorId: id, editorKind: kind, type: preset.type || kind, position: [...position], scale: [...preset.scale], yaw: options.yaw || 0, color: [...preset.color], meta: { label: preset.label }, solid: preset.solid !== false };
    const suggestedRole = {
      charger: 'CHARGE', charging_dock: 'CHARGE', station: 'WORK', conveyor: 'WORK',
      nurse_desk: 'WORK', pallet_stack: 'DROPOFF', baggage_cart: 'DROPOFF', hospital_cart: 'DROPOFF'
    }[kind];
    if (suggestedRole) object.operational_role = suggestedRole;
    const collider = { position: object.position, scale: object.scale, yaw: object.yaw, editorId: id };
    if (object.solid && !canPlaceSolid(collider, this.scene.solids)) return null;
    this.history.mutate(patch => patch.created.push(object)); this.selectedId = id; this.refresh(); return id;
  }

  setOperationalRole(id, role) {
    const object = this.history.present.created.find(item => item.id === id);
    if (!object || (role !== null && !operationalRolesFor(object).includes(role))) return false;
    this.history.mutate(patch => {
      const item = patch.created.find(candidate => candidate.id === id);
      if (role === null) delete item.operational_role;
      else item.operational_role = role;
    });
    this.refresh();
    return true;
  }

  setZoneOperationalRole(id, role) {
    if (role !== null && role !== 'WORK') return false;
    if (!this.history.present.zones?.some(zone => zone.id === id)) return false;
    this.history.mutate(patch => {
      const zone = patch.zones.find(item => item.id === id);
      if (role === null) delete zone.operational_role;
      else zone.operational_role = role;
    });
    this.refresh();
    return true;
  }

  assignRobot(robotId, selection, payloadKg, speedMps) {
    const robot = this.scene.staticObjects.find(item => item.id === robotId);
    const type = robot && ASSIGNABLE_ROBOTS[robot.kind];
    if (!type) return { ok: false, reason: 'Выберите размещённого робота из каталога.' };
    const profile = robotProfile(type);
    if (!Number.isFinite(payloadKg) || payloadKg < 0 || payloadKg > profile.maxLoadKg) return { ok: false, reason: `Груз должен быть от 0 до ${profile.maxLoadKg} кг.` };
    if (!Number.isFinite(speedMps) || speedMps < .1 || speedMps > 3) return { ok: false, reason: 'Скорость должна быть от 0,1 до 3 м/с.' };
    if (!selection.dropoffId) return { ok: false, reason: 'Для перевозки груза нужна точка DROPOFF.' };
    const freeScene = { ...this.scene, solids: this.scene.solids.filter(solid => solid.editorId !== robotId) };
    const path = planOperationalPath(freeScene, selection, profile.radius);
    if (!path.ok) return path;
    this.history.mutate(patch => {
      patch.assignments ||= [];
      patch.assignments = patch.assignments.filter(item => item.robot_id !== robotId);
      patch.assignments.push({ robot_id: robotId, charge_id: selection.chargeId, work_id: selection.workId,
        dropoff_id: selection.dropoffId, payload_kg: payloadKg, speed_mps: speedMps });
    });
    this.refresh();
    return { ok: true, distance: path.distance };
  }

  removeRobotAssignment(robotId) {
    if (!this.history.present.assignments?.some(item => item.robot_id === robotId)) return false;
    this.history.mutate(patch => { patch.assignments = patch.assignments.filter(item => item.robot_id !== robotId); });
    this.refresh();
    return true;
  }

  importDxfObjects(objects, metadata = null) {
    if (!Array.isArray(objects) || !objects.length || objects.length > 300) throw new Error('DXF должен содержать от 1 до 300 поддержанных сегментов.');
    const additions = objects.map(part => {
      const instanceId = crypto.randomUUID(), id = `user:cad:${instanceId}`;
      return { ...clone(part), id, instance_id: instanceId, editorId: id, editorKind: part.kind };
    });
    const next = clone(this.history.present);
    next.created.push(...additions);
    if (metadata) next.cad = clone(metadata);
    applyScenePatch(this.baseScene, next);
    this.history.commit(next);
    this.refresh();
    return additions.length;
  }

  setEconomicsInputs(inputs) {
    validateEconomicsInputs(inputs);
    this.history.mutate(patch => { patch.economics = clone(inputs); });
    this.refresh();
  }

  wallSegmentPlan(start, end, options = {}) {
    if (![start, end].every(point => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite))) return null;
    const dx = end[0] - start[0], dz = end[1] - start[1];
    const length = Math.hypot(dx, dz);
    const door = options.door === true;
    const doorWidth = 1.2, height = 3, thickness = .3;
    if (length < (door ? doorWidth + 1 : .5)) return null;
    const ux = dx / length, uz = dz / length, yaw = -Math.atan2(dz, dx);
    const center = (distance) => [start[0] + ux * distance, height / 2, start[1] + uz * distance];
    const wall = (distance, segmentLength) => ({ kind: 'wall', type: 'wall', position: center(distance),
      scale: [segmentLength, height, thickness], yaw, color: [.73, .78, .75],
      meta: { label: 'Стена · сегмент' }, solid: true });
    const parts = door ? [wall((length - doorWidth) / 4, (length - doorWidth) / 2),
      wall((3 * length + doorWidth) / 4, (length - doorWidth) / 2),
      { kind: 'door_frame', type: 'decor', position: [start[0] + dx / 2, 1.2, start[1] + dz / 2],
        scale: [doorWidth, 2.4, .45], yaw, color: [.62, .72, .70],
        meta: { label: 'Дверной проём' }, solid: false }]
      : [wall(length / 2, length)];
    const wallIds = new Set(this.scene.staticObjects.filter(object => object.type === 'wall').map(object => object.editorId));
    const blockers = this.scene.solids.filter(solid => !wallIds.has(solid.editorId));
    if (parts.some(part => {
      const extent = solidExtents(part);
      return Math.abs(part.position[0]) + extent.x > this.scene.config.width / 2 ||
        Math.abs(part.position[2]) + extent.z > this.scene.config.depth / 2 ||
        (part.solid && !canPlaceSolid(part, blockers));
    })) return null;
    return parts;
  }

  createWallSegment(start, end, options = {}) {
    const plan = this.wallSegmentPlan(start, end, options);
    if (!plan) return null;
    const objects = plan.map(part => {
      const instanceId = crypto.randomUUID();
      const id = `user:${part.kind}:${instanceId}`;
      return { id, instance_id: instanceId, editorId: id, editorKind: part.kind, ...part };
    });
    this.history.mutate(patch => patch.created.push(...objects));
    this.selectedId = objects[0].id;
    this.refresh();
    return objects.map(object => object.id);
  }

  delete(id = this.selectedId) {
    const room = this.roomForPart(id);
    if (room) return this.deleteRoom(room.id);
    if (!this.entity(id)) return false;
    this.history.mutate(patch => {
      const index = patch.created.findIndex(item => item.id === id);
      if (index >= 0) patch.created.splice(index, 1);
      else if (!patch.deleted.includes(id)) patch.deleted.push(id);
      delete patch.objects[id];
      if (patch.assignments?.some(item => item.robot_id === id)) patch.assignments = patch.assignments.filter(item => item.robot_id !== id);
    });
    if (this.selectedId === id) this.selectedId = null;
    this.refresh(); return true;
  }

  duplicate(id = this.selectedId, offset = [1, 0, 1]) {
    const entity = this.entity(id); if (!entity) return null;
    const preset = BUILD_CATALOG.find(item => item.kind === entity.kind) || BUILD_CATALOG.at(-1);
    const instanceId = crypto.randomUUID();
    const createdId = `user:${entity.kind}:${instanceId}`;
    const object = { id: createdId, instance_id: instanceId, kind: entity.kind, editorId: createdId, editorKind: entity.kind, type: preset.type || entity.kind, position: entity.position.map((value, axis) => value + offset[axis]), scale: [...entity.scale], yaw: entity.yaw, color: [...(entity.parts[0].color || preset.color)], meta: { label: `${entity.label} (копия)` }, solid: preset.solid !== false };
    if (object.solid && !canPlaceSolid({ ...object, editorId: createdId }, this.scene.solids)) return null;
    this.history.mutate(patch => patch.created.push(object));
    this.selectedId = createdId; this.refresh(); return createdId;
  }

  editRobot(routeId, edit) {
    const route = this.scene.routes.find(item => item.id === routeId); if (!route) return false;
    if (edit.robotType && !compatibleRobotTypes(this.scene.config.template).includes(edit.robotType)) return false;
    this.history.mutate(patch => { patch.robots[routeId] = { ...(patch.robots[routeId] || {}), ...clone(edit) }; });
    this.refresh(); return true;
  }

  addZone(name, points) {
    if (!validZonePolygon(points, this.scene.config.width, this.scene.config.depth)) return null;
    const trimmed = String(name || '').trim();
    if (!trimmed || trimmed.length > 120 || (this.history.present.zones?.length || 0) >= 64) return null;
    const id = `zone:${crypto.randomUUID()}`;
    this.history.mutate(patch => { patch.zones ||= []; patch.zones.push({ id, name: trimmed, points: clone(points) }); });
    this.refresh();
    return id;
  }

  addRoom(name, points) {
    if (!validRoomPolygon(points, this.scene.config.width, this.scene.config.depth)) return null;
    const trimmed = String(name || '').trim();
    if (!trimmed || trimmed.length > 120 || (this.history.present.rooms?.length || 0) >= 64) return null;
    const plans = points.map((point, index) => this.wallSegmentPlan(point, points[(index + 1) % points.length]));
    if (plans.some(plan => !plan || plan.length !== 1)) return null;
    const id = `room:${crypto.randomUUID()}`;
    const walls = plans.map(plan => {
      const instanceId = crypto.randomUUID();
      const wallId = `user:wall:${instanceId}`;
      return { id: wallId, instance_id: instanceId, editorId: wallId, editorKind: 'wall',
        ...plan[0], meta: { label: `Стена комнаты «${trimmed}»` } };
    });
    this.history.mutate(patch => {
      patch.created.push(...walls);
      patch.rooms ||= [];
      patch.rooms.push({ id, name: trimmed, points: clone(points), wall_ids: walls.map(wall => wall.id) });
    });
    this.refresh();
    return id;
  }

  roomForPart(id) {
    return this.history.present.rooms?.find(room => room.wall_ids.includes(id) ||
      room.doors?.some(door => door.right_wall_id === id || door.frame_id === id)) || null;
  }

  toggleRoomDoor(roomId, edge) {
    const room = this.history.present.rooms?.find(item => item.id === roomId);
    if (!room || !Number.isInteger(edge) || edge < 0 || edge >= room.points.length) return false;
    const current = room.doors?.find(door => door.edge === edge);
    const plan = this.wallSegmentPlan(room.points[edge], room.points[(edge + 1) % room.points.length], { door: !current });
    if (!plan || plan.length !== (current ? 1 : 3)) return false;
    const primaryId = room.wall_ids[edge];
    if (!this.history.present.created.some(item => item.id === primaryId)) return false;
    const extras = current ? [] : plan.slice(1).map(part => {
      const instanceId = crypto.randomUUID();
      const id = `user:${part.kind}:${instanceId}`;
      return { id, instance_id: instanceId, editorId: id, editorKind: part.kind, ...part };
    });
    this.history.mutate(patch => {
      const patchRoom = patch.rooms.find(item => item.id === roomId);
      const primary = patch.created.find(item => item.id === primaryId);
      Object.assign(primary, plan[0], { meta: { label: `Стена комнаты «${patchRoom.name}»` } });
      if (current) {
        const removed = new Set([current.right_wall_id, current.frame_id]);
        patch.created = patch.created.filter(item => !removed.has(item.id));
        patchRoom.doors = patchRoom.doors.filter(door => door.edge !== edge);
      } else {
        patch.created.push(...extras);
        patchRoom.doors ||= [];
        patchRoom.doors.push({ edge, right_wall_id: extras[0].id, frame_id: extras[1].id });
      }
    });
    this.selectedId = primaryId;
    this.refresh();
    return true;
  }

  deleteRoom(id) {
    const room = this.history.present.rooms?.find(item => item.id === id);
    if (!room) return false;
    const wallIds = new Set([...room.wall_ids, ...(room.doors || []).flatMap(door => [door.right_wall_id, door.frame_id])]);
    this.history.mutate(patch => {
      patch.rooms = patch.rooms.filter(item => item.id !== id);
      patch.created = patch.created.filter(item => !wallIds.has(item.id));
      wallIds.forEach(wallId => delete patch.objects[wallId]);
    });
    if (wallIds.has(this.selectedId)) this.selectedId = null;
    this.refresh();
    return true;
  }

  deleteZone(id) {
    if (!this.history.present.zones?.some(zone => zone.id === id)) return false;
    this.history.mutate(patch => { patch.zones = patch.zones.filter(zone => zone.id !== id); });
    this.refresh();
    return true;
  }

  undo() { this.history.undo(); this.refresh(); return this.scene; }
  redo() { this.history.redo(); this.refresh(); return this.scene; }
  reset() {
    this.selectedId = null;
    const base = this.history.present.base;
    this.history.reset(createScenePatch(this.baseScene.config, {
      revisionId: base.revision_id,
      visualFingerprint: base.visual_fingerprint,
      zoneId: base.zone_id
    }));
    return this.refresh();
  }
}

export function cameraRay(camera) {
  const cp = Math.cos(camera.pitch);
  return { origin: camera.position, direction: [Math.sin(camera.yaw) * cp, Math.sin(camera.pitch), -Math.cos(camera.yaw) * cp] };
}

export function rayGroundPoint(camera, maxDistance = 60) {
  const ray = cameraRay(camera);
  if (ray.direction[1] >= -.015) return [ray.origin[0] + ray.direction[0] * 8, .5, ray.origin[2] + ray.direction[2] * 8];
  const distance = Math.min(maxDistance, Math.max(0, -ray.origin[1] / ray.direction[1]));
  return [ray.origin[0] + ray.direction[0] * distance, .5, ray.origin[2] + ray.direction[2] * distance];
}

export function pickEntity(camera, entities, robots = [], maxDistance = 45) {
  const ray = cameraRay(camera); let best = null;
  const targets = [...entities, ...robots.map(robot => ({ id: `robot:${robot.id}`, kind: 'robot', label: robot.label, position: robot.position, scale: [robot.radius * 2, 1.4, robot.radius * 2], robot }))];
  for (const target of targets) {
    const center = target.position; const radius = Math.hypot(...target.scale) / 2;
    const to = center.map((value, axis) => value - ray.origin[axis]);
    const along = to.reduce((sum, value, axis) => sum + value * ray.direction[axis], 0);
    if (along < 0 || along > maxDistance) continue;
    const closest = Math.hypot(...to.map((value, axis) => value - ray.direction[axis] * along));
    if (closest <= radius && (!best || along < best.distance)) best = { ...target, distance: along };
  }
  return best;
}
