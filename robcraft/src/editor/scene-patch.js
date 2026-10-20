import { robotProfile, robotTypesForTemplate } from '../world/robot-catalog.js';
import { canPlaceSolid } from './collisions.js';
import { validZonePolygon } from './map-view.js';
import { validRoomPolygon } from './room-polygon.js';
import { ASSIGNABLE_ROBOTS, operationalRolesFor, planOperationalPath } from './operational.js';
import { validateEconomicsInputs } from './live-economics.js';

export const SCENE_PATCH_VERSION = 'robcraft-scene-patch-v1';
const EDITABLE_TYPES = new Set(['wall', 'rack', 'cargo', 'station', 'charger', 'checkin', 'seat', 'baggage', 'bed', 'reception', 'supply', 'fence', 'decor']);

const clone = value => JSON.parse(JSON.stringify(value));
const round = value => Math.round(value * 10000) / 10000;
const canonicalJson = value => JSON.stringify(value, (_, item) => {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
  return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]));
});

const PATCH_FIELDS = new Set(['format', 'base', 'objects', 'created', 'deleted', 'robots', 'zones', 'rooms', 'assignments', 'economics', 'cad']);
const PATCH_BASE_FIELDS = new Set(['config', 'revision_id', 'visual_fingerprint', 'zone_id']);

function assertPlainObject(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError(`${path} должен быть объектом`);
}

function assertExactFields(value, allowed, path) {
  assertPlainObject(value, path);
  const unknown = Object.keys(value).filter(key => !allowed.has(key));
  if (unknown.length) throw new TypeError(`${path}: неизвестные поля: ${unknown.join(', ')}`);
}

function assertNumberArray(value, lengths, path) {
  if (!Array.isArray(value) || !lengths.includes(value.length) || value.some(item => typeof item !== 'number' || !Number.isFinite(item))) throw new TypeError(`${path} должен быть числовым массивом длины ${lengths.join(' или ')}`);
}

export function scenarioVisualFingerprint(spec) {
  const source = JSON.stringify({
    schema_version: spec.schema_version,
    template: spec.template,
    seed: spec.seed,
    facility: spec.facility,
    profile: spec.profile,
    operating_windows: spec.operating_windows,
    zones: spec.zones,
    routes: spec.routes,
    fleet: spec.fleet,
    task_profiles: spec.task_profiles,
    tasks: spec.tasks
  });
  let hash = 2166136261;
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `visual_${(hash >>> 0).toString(16).padStart(8, '0')}`;
}

export function createScenePatch(config, binding = {}) {
  const base = { config: clone(config) };
  if (binding.revisionId !== undefined) base.revision_id = binding.revisionId;
  if (binding.visualFingerprint !== undefined) base.visual_fingerprint = binding.visualFingerprint;
  if (binding.zoneId !== undefined) base.zone_id = binding.zoneId;
  return { format: SCENE_PATCH_VERSION, base, objects: {}, created: [], deleted: [], robots: {}, zones: [], rooms: [], assignments: [] };
}

export function validateScenePatch(patch) {
  assertExactFields(patch, PATCH_FIELDS, 'ScenePatch');
  if (patch.format !== SCENE_PATCH_VERSION) throw new TypeError(`Неподдерживаемый формат ScenePatch: ${patch.format || 'отсутствует'}`);
  assertExactFields(patch.base, PATCH_BASE_FIELDS, 'ScenePatch.base');
  assertPlainObject(patch.base.config, 'ScenePatch.base.config');
  assertPlainObject(patch.objects, 'ScenePatch.objects');
  assertPlainObject(patch.robots, 'ScenePatch.robots');
  if (!Array.isArray(patch.created) || !Array.isArray(patch.deleted)) throw new TypeError('ScenePatch.created и ScenePatch.deleted должны быть массивами');
  if (patch.assignments !== undefined) {
    if (!Array.isArray(patch.assignments) || patch.assignments.length > 64) throw new TypeError('ScenePatch.assignments должен содержать не более 64 заданий');
    const used = new Set();
    patch.assignments.forEach((item, index) => {
      assertExactFields(item, new Set(['robot_id', 'charge_id', 'work_id', 'dropoff_id', 'payload_kg', 'speed_mps']), `ScenePatch.assignments.${index}`);
      if (![item.robot_id, item.charge_id, item.work_id, item.dropoff_id].every(id => typeof id === 'string' && id.length > 0)) throw new TypeError('ScenePatch.assignments содержит неверные ссылки');
      if (used.has(item.robot_id)) throw new TypeError('ScenePatch.assignments содержит повторное назначение робота');
      used.add(item.robot_id);
      if (typeof item.payload_kg !== 'number' || !Number.isFinite(item.payload_kg) || item.payload_kg < 0 || item.payload_kg > 2000) throw new TypeError('ScenePatch.assignments содержит неверный груз');
      if (typeof item.speed_mps !== 'number' || !Number.isFinite(item.speed_mps) || item.speed_mps < .1 || item.speed_mps > 3) throw new TypeError('ScenePatch.assignments содержит неверную скорость');
    });
  }
  if (patch.economics !== undefined) validateEconomicsInputs(patch.economics);
  if (patch.cad !== undefined) {
    assertExactFields(patch.cad, new Set(['file_name', 'unit_meters', 'wall_height_m', 'wall_layers', 'obstacle_layers', 'unsupported_entities', 'malformed_entities']), 'ScenePatch.cad');
    if (typeof patch.cad.file_name !== 'string' || !/^[^\\/]{1,200}\.dxf$/i.test(patch.cad.file_name) ||
        ![patch.cad.unit_meters, patch.cad.wall_height_m].every(value => typeof value === 'number' && Number.isFinite(value) && value > 0) ||
        ![patch.cad.wall_layers, patch.cad.obstacle_layers].every(value => Array.isArray(value) && value.length <= 32 && value.every(layer => typeof layer === 'string' && layer.length > 0 && layer.length <= 120)) ||
        ![patch.cad.unsupported_entities, patch.cad.malformed_entities].every(value => Number.isInteger(value) && value >= 0)) throw new TypeError('ScenePatch.cad содержит неверное происхождение чертежа');
  }
  if (patch.zones !== undefined) {
    if (!Array.isArray(patch.zones) || patch.zones.length > 64) throw new TypeError('ScenePatch.zones должен содержать не более 64 зон');
    const ids = new Set();
    patch.zones.forEach((zone, index) => {
      assertExactFields(zone, new Set(['id', 'name', 'points', 'operational_role']), `ScenePatch.zones.${index}`);
      if (!/^zone:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(zone.id) || ids.has(zone.id)) throw new TypeError('ScenePatch.zones содержит неверный или повторный ID');
      ids.add(zone.id);
      if (typeof zone.name !== 'string' || !zone.name.trim() || zone.name.length > 120) throw new TypeError('ScenePatch.zones содержит неверное имя');
      if (!Array.isArray(zone.points) || zone.points.length < 3 || zone.points.length > 64) throw new TypeError('ScenePatch.zones содержит неверный контур');
      zone.points.forEach((point, pointIndex) => assertNumberArray(point, [2], `ScenePatch.zones.${index}.points.${pointIndex}`));
      if (!validZonePolygon(zone.points, patch.base.config.width, patch.base.config.depth)) throw new TypeError('ScenePatch.zones содержит контур за границей площадки или нулевой площади');
      if (zone.operational_role !== undefined && zone.operational_role !== 'WORK') throw new TypeError('ScenePatch.zones содержит неверную операционную роль');
    });
  }
  if (patch.rooms !== undefined) {
    if (!Array.isArray(patch.rooms) || patch.rooms.length > 64) throw new TypeError('ScenePatch.rooms должен содержать не более 64 комнат');
    const ids = new Set();
    const linkedWalls = new Set();
    patch.rooms.forEach((room, index) => {
      assertExactFields(room, new Set(['id', 'name', 'points', 'wall_ids', 'doors']), `ScenePatch.rooms.${index}`);
      if (!/^room:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(room.id) || ids.has(room.id)) throw new TypeError('ScenePatch.rooms содержит неверный или повторный ID');
      ids.add(room.id);
      if (typeof room.name !== 'string' || !room.name.trim() || room.name.length > 120) throw new TypeError('ScenePatch.rooms содержит неверное имя');
      if (!Array.isArray(room.points) || room.points.length < 3 || room.points.length > 64) throw new TypeError('ScenePatch.rooms содержит неверный контур');
      room.points.forEach((point, pointIndex) => assertNumberArray(point, [2], `ScenePatch.rooms.${index}.points.${pointIndex}`));
      if (!validRoomPolygon(room.points, patch.base.config.width, patch.base.config.depth)) throw new TypeError('ScenePatch.rooms содержит некорректный контур');
      if (!Array.isArray(room.wall_ids) || room.wall_ids.length !== room.points.length || new Set(room.wall_ids).size !== room.wall_ids.length ||
          room.wall_ids.some(id => typeof id !== 'string' || !patch.created.some(item => item.id === id && item.type === 'wall'))) throw new TypeError('ScenePatch.rooms содержит неверные ссылки на стены');
      if (room.wall_ids.some(id => linkedWalls.has(id) || Object.hasOwn(patch.objects, id))) throw new TypeError('Стена комнаты изменена отдельно или принадлежит двум комнатам');
      room.wall_ids.forEach(id => linkedWalls.add(id));
      if (room.doors !== undefined) {
        if (!Array.isArray(room.doors) || room.doors.length > room.points.length) throw new TypeError('ScenePatch.rooms содержит неверные проёмы');
        const edges = new Set();
        room.doors.forEach(door => {
          assertExactFields(door, new Set(['edge', 'right_wall_id', 'frame_id']), 'ScenePatch.rooms.doors');
          if (!Number.isInteger(door.edge) || door.edge < 0 || door.edge >= room.points.length || edges.has(door.edge)) throw new TypeError('ScenePatch.rooms содержит неверное ребро проёма');
          edges.add(door.edge);
          for (const [id, kind] of [[door.right_wall_id, 'wall'], [door.frame_id, 'door_frame']]) {
            if (typeof id !== 'string' || linkedWalls.has(id) || Object.hasOwn(patch.objects, id) ||
                !patch.created.some(item => item.id === id && item.kind === kind)) throw new TypeError('ScenePatch.rooms содержит неверные части проёма');
            linkedWalls.add(id);
          }
        });
      }
    });
  }
  if (patch.base.revision_id !== undefined && !/^calc_[0-9a-f]{16}$/.test(patch.base.revision_id)) throw new TypeError('ScenePatch.base.revision_id имеет неверный формат');
  if (patch.base.visual_fingerprint !== undefined && !/^visual_[0-9a-f]{8}$/.test(patch.base.visual_fingerprint)) throw new TypeError('ScenePatch.base.visual_fingerprint имеет неверный формат');
  if (patch.base.zone_id !== undefined && (typeof patch.base.zone_id !== 'string' || !patch.base.zone_id)) throw new TypeError('ScenePatch.base.zone_id должен быть непустой строкой');
  Object.entries(patch.objects).forEach(([id, change]) => {
    assertExactFields(change, new Set(['position', 'scale', 'yaw']), `ScenePatch.objects.${id}`);
    if (change.position !== undefined) assertNumberArray(change.position, [3], `ScenePatch.objects.${id}.position`);
    if (change.scale !== undefined) assertNumberArray(change.scale, [3], `ScenePatch.objects.${id}.scale`);
    if (change.yaw !== undefined && (typeof change.yaw !== 'number' || !Number.isFinite(change.yaw))) throw new TypeError(`ScenePatch.objects.${id}.yaw должен быть числом`);
  });
  patch.created.forEach((item, index) => {
    assertExactFields(item, new Set(['id', 'instance_id', 'kind', 'editorId', 'editorKind', 'type', 'position', 'scale', 'yaw', 'color', 'meta', 'solid', 'operational_role']), `ScenePatch.created.${index}`);
    if (typeof item.id !== 'string' || typeof item.kind !== 'string' || typeof item.type !== 'string') throw new TypeError(`ScenePatch.created.${index} содержит неверный идентификатор или тип`);
    if (item.instance_id !== undefined && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(item.instance_id)) throw new TypeError(`ScenePatch.created.${index}.instance_id имеет неверный формат`);
    assertNumberArray(item.position, [3], `ScenePatch.created.${index}.position`);
    assertNumberArray(item.scale, [3], `ScenePatch.created.${index}.scale`);
    if (item.color !== undefined) assertNumberArray(item.color, [3], `ScenePatch.created.${index}.color`);
    if (item.meta !== undefined) assertExactFields(item.meta, new Set(['label']), `ScenePatch.created.${index}.meta`);
    if (item.operational_role !== undefined && !operationalRolesFor(item).includes(item.operational_role)) throw new TypeError(`ScenePatch.created.${index} содержит неверную операционную роль`);
  });
  if (patch.deleted.some(id => typeof id !== 'string')) throw new TypeError('ScenePatch.deleted должен содержать строковые id');
  Object.entries(patch.robots).forEach(([id, edit]) => {
    assertExactFields(edit, new Set(['robotType', 'points', 'chargePosition', 'startPosition']), `ScenePatch.robots.${id}`);
    if (edit.robotType !== undefined && typeof edit.robotType !== 'string') throw new TypeError(`ScenePatch.robots.${id}.robotType должен быть строкой`);
    if (edit.points !== undefined) {
      if (!Array.isArray(edit.points)) throw new TypeError(`ScenePatch.robots.${id}.points должен быть массивом`);
      edit.points.forEach((point, index) => assertNumberArray(point, [2], `ScenePatch.robots.${id}.points.${index}`));
    }
    if (edit.chargePosition !== undefined) assertNumberArray(edit.chargePosition, [2], `ScenePatch.robots.${id}.chargePosition`);
    if (edit.startPosition !== undefined) assertNumberArray(edit.startPosition, [2], `ScenePatch.robots.${id}.startPosition`);
  });
  return patch;
}

export function scenePatchHasChanges(patch) {
  validateScenePatch(patch);
  return Object.keys(patch.objects).length > 0 || patch.created.length > 0 || patch.deleted.length > 0 || Object.keys(patch.robots).length > 0 || (patch.zones?.length || 0) > 0 || (patch.rooms?.length || 0) > 0 || (patch.assignments?.length || 0) > 0 || Object.keys(patch.economics || {}).length > 0 || Boolean(patch.cad);
}

export function scenePatchSummary(patch) {
  validateScenePatch(patch);
  return Object.freeze({ objects: Object.keys(patch.objects).length, created: patch.created.length, deleted: patch.deleted.length, robots: Object.keys(patch.robots).length, zones: patch.zones?.length || 0, rooms: patch.rooms?.length || 0, assignments: patch.assignments?.length || 0, economics: Object.keys(patch.economics || {}).length });
}

export function assertScenePatchCompatible(patch, binding) {
  validateScenePatch(patch);
  if (!patch.base.revision_id || !patch.base.visual_fingerprint) throw new TypeError('ScenePatch не привязан к расчётной ревизии');
  if (patch.base.revision_id !== binding.revisionId) throw new TypeError(`ScenePatch относится к другой ревизии: ${patch.base.revision_id}`);
  if (patch.base.visual_fingerprint !== binding.visualFingerprint) throw new TypeError('ScenePatch относится к другой визуальной базе');
  if (binding.zoneId !== undefined && patch.base.zone_id !== binding.zoneId) throw new TypeError(`ScenePatch относится к другой зоне: ${patch.base.zone_id || 'не указана'}`);
  return patch;
}

export function rebindScenePatch(patch, binding) {
  validateScenePatch(patch);
  const rebound = clone(patch);
  rebound.base.revision_id = binding.revisionId;
  rebound.base.visual_fingerprint = binding.visualFingerprint;
  if (binding.zoneId !== undefined) rebound.base.zone_id = binding.zoneId;
  return rebound;
}

export function normalizeEditableScene(scene) {
  const counters = {};
  scene.staticObjects.forEach((object, index) => {
    if (!EDITABLE_TYPES.has(object.type) && !object.editorId) return;
    const kind = object.editorKind || object.type;
    counters[kind] = (counters[kind] || 0) + 1;
    object.editorId ||= `base:${kind}:${String(counters[kind]).padStart(3, '0')}`;
    object.editorKind ||= kind;
    object.baseIndex = index;
  });
  scene.solids.forEach(solid => {
    if (solid.editorId) return;
    const match = scene.staticObjects.find(object => object.editorId && object.position.every((v, i) => Math.abs(v - solid.position[i]) < .0001) && object.scale.every((v, i) => Math.abs(v - solid.scale[i]) < .0001));
    if (match) solid.editorId = match.editorId;
  });
  return scene;
}

function bounds(parts) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  parts.forEach(part => part.position.forEach((value, axis) => {
    min[axis] = Math.min(min[axis], value - part.scale[axis] / 2);
    max[axis] = Math.max(max[axis], value + part.scale[axis] / 2);
  }));
  return { position: min.map((value, axis) => (value + max[axis]) / 2), scale: min.map((value, axis) => max[axis] - value) };
}

export function listEditableEntities(scene) {
  const groups = new Map();
  scene.staticObjects.forEach(object => {
    if (!object.editorId) return;
    if (!groups.has(object.editorId)) groups.set(object.editorId, []);
    groups.get(object.editorId).push(object);
  });
  return [...groups].map(([id, parts]) => ({ id, kind: parts[0].editorKind || parts[0].type, label: parts[0].meta?.label || labelFor(parts[0].editorKind || parts[0].type), ...bounds(parts), yaw: parts[0].editorYaw ?? (parts[0].yaw || 0), parts }));
}

function labelFor(kind) {
  return ({ wall: 'Стена', rack: 'Стеллаж', cargo: 'Паллета / груз', station: 'Рабочая станция', charger: 'Зарядная позиция', fence: 'Ограждение', decor: 'Декоративный блок', robot: 'Робот' })[kind] || 'Оборудование';
}

function transformPart(part, original, target) {
  const deltaYaw = (target.yaw || 0) - (original.yaw || 0);
  const ratio = target.scale.map((value, axis) => value / Math.max(.001, original.scale[axis]));
  const offset = part.position.map((value, axis) => (value - original.position[axis]) * ratio[axis]);
  const x = offset[0] * Math.cos(deltaYaw) + offset[2] * Math.sin(deltaYaw);
  const z = -offset[0] * Math.sin(deltaYaw) + offset[2] * Math.cos(deltaYaw);
  part.position = [round(target.position[0] + x), round(target.position[1] + offset[1]), round(target.position[2] + z)];
  part.scale = part.scale.map((value, axis) => round(value * ratio[axis]));
  part.yaw = round((part.yaw || 0) + deltaYaw);
  part.editorYaw = target.yaw || 0;
}

export function rebuildSceneSolids(scene) {
  const retained = scene.solids.filter(solid => !solid.editorId);
  const byId = new Map(scene.solids.filter(solid => solid.editorId).map(solid => [solid.editorId, solid]));
  for (const entity of listEditableEntities(scene)) {
    const prior = byId.get(entity.id);
    if (prior || entity.parts.some(part => part.solid)) retained.push({ position: [...entity.position], scale: [...entity.scale], yaw: entity.yaw, editorId: entity.id });
  }
  scene.solids = retained;
  return scene.solids;
}

export function applyScenePatch(baseScene, patch) {
  validateScenePatch(patch);
  const scene = normalizeEditableScene(clone(baseScene));
  const originals = new Map(listEditableEntities(scene).map(entity => [entity.id, clone(entity)]));
  Object.entries(patch.objects || {}).forEach(([id, change]) => {
    const original = originals.get(id);
    if (!original) return;
    const target = { position: change.position || original.position, scale: change.scale || original.scale, yaw: change.yaw ?? original.yaw };
    listEditableEntities(scene).find(entity => entity.id === id)?.parts.forEach(part => transformPart(part, original, target));
  });
  const deleted = new Set(patch.deleted || []);
  scene.staticObjects = scene.staticObjects.filter(object => !deleted.has(object.editorId));
  for (const created of patch.created || []) scene.staticObjects.push({ ...clone(created), editorId: created.id, editorKind: created.kind, solid: created.solid !== false });
  scene.routes.forEach(route => {
    const edit = patch.robots?.[route.id];
    if (!edit) return;
    if (edit.robotType) Object.assign(route, robotProfile(edit.robotType));
    if (edit.points) route.points = clone(edit.points);
    if (edit.chargePosition) route.points[route.chargeWaypoint ?? 0] = clone(edit.chargePosition);
    if (edit.startPosition) {
      route.points.unshift(clone(edit.startPosition));
      route.pickupWaypoint = (route.pickupWaypoint ?? 2) + 1;
      route.dropWaypoint = (route.dropWaypoint ?? 4) + 1;
      route.chargeWaypoint = (route.chargeWaypoint ?? 0) + 1;
      route.phase = 0;
    }
  });
  rebuildSceneSolids(scene);
  scene.editorZones = clone(patch.zones || []);
  scene.editorRooms = clone(patch.rooms || []);
  const editedIds = new Set([...Object.keys(patch.objects || {}), ...(patch.created || []).filter(item => item.solid !== false).map(item => item.id)]);
  const wallIds = new Set(scene.staticObjects.filter(object => object.type === 'wall').map(object => object.editorId));
  for (const id of editedIds) {
    const solid = scene.solids.find(item => item.editorId === id);
    const blockers = id.startsWith('user:cad:') ? scene.solids.filter(item => !item.editorId?.startsWith('user:cad:'))
      : wallIds.has(id) ? scene.solids.filter(item => !wallIds.has(item.editorId)) : scene.solids;
    if (solid && !canPlaceSolid(solid, blockers, id)) throw new Error(`ScenePatch содержит конфликтующее размещение: ${id}`);
  }
  scene.editorAssignments = [];
  for (const assignment of patch.assignments || []) {
    const robot = scene.staticObjects.find(item => item.id === assignment.robot_id);
    const type = robot && ASSIGNABLE_ROBOTS[robot.kind];
    if (!type) { scene.editorAssignments.push({ ...assignment, ok: false, reason: 'Размещённый робот удалён или его тип изменён.' }); continue; }
    const profile = robotProfile(type);
    if (assignment.payload_kg > profile.maxLoadKg) { scene.editorAssignments.push({ ...assignment, ok: false, reason: 'Груз превышает грузоподъёмность робота.' }); continue; }
    // The placed asset is an editable deployment marker. Its dynamic counterpart occupies the route.
    const markerSolids = scene.solids.filter(solid => solid.editorId === assignment.robot_id);
    scene.solids = scene.solids.filter(solid => solid.editorId !== assignment.robot_id);
    robot.runtimeHidden = true;
    const plan = planOperationalPath(scene, { chargeId: assignment.charge_id, workId: assignment.work_id, dropoffId: assignment.dropoff_id }, profile.radius);
    if (!plan.ok) { robot.runtimeHidden = false; scene.solids.push(...markerSolids); scene.editorAssignments.push({ ...assignment, ok: false, reason: plan.reason }); continue; }
    const routeId = Math.max(0, ...scene.routes.map(route => route.id)) + 1;
    scene.routes.push({ id: routeId, ...profile, kind: scene.config.template || 'warehouse', points: plan.points,
      chargeWaypoint: 0, pickupWaypoint: plan.waypointIndices[1], dropWaypoint: plan.waypointIndices[2],
      speed: assignment.speed_mps, phase: 0, unitsPerTrip: 1, assignmentRobotId: assignment.robot_id });
    scene.editorAssignments.push({ ...assignment, ok: true, routeId, distance: plan.distance });
  }
  scene.scenePatch = clone(patch);
  return scene;
}

export function exportSceneDocument(patch, inventory = null) {
  const document = { engine: 'robcraft', documentVersion: 1, base: clone(patch.base), scenePatch: clone(patch) };
  if (inventory) document.inventory = clone(inventory);
  return JSON.stringify(document, null, 2);
}

export function importSceneDocument(source) {
  const document = typeof source === 'string' ? JSON.parse(source) : clone(source);
  assertExactFields(document, new Set(['engine', 'documentVersion', 'base', 'scenePatch', 'inventory']), 'SceneDocument');
  if (document.engine !== 'robcraft' || document.documentVersion !== 1) throw new Error('Файл не является сценой RobCraft v1');
  validateScenePatch(document.scenePatch);
  if (canonicalJson(document.base) !== canonicalJson(document.scenePatch.base)) throw new TypeError('SceneDocument.base не совпадает с базой ScenePatch');
  if (document.inventory) {
    assertExactFields(document.inventory, new Set(['slots', 'active']), 'SceneDocument.inventory');
    if (!Array.isArray(document.inventory.slots) || document.inventory.slots.length !== 9 || document.inventory.slots.some(item => item !== null && typeof item !== 'string')) throw new TypeError('Неверные слоты инвентаря');
    if (document.inventory.active !== null && (!Number.isInteger(document.inventory.active) || document.inventory.active < 0 || document.inventory.active > 8)) throw new TypeError('Неверный активный слот');
  }
  return { baseConfig: clone(document.base.config), patch: clone(document.scenePatch), inventory: document.inventory ? clone(document.inventory) : null };
}

export function compatibleRobotTypes(template) { return [...robotTypesForTemplate(template)]; }

export class SceneHistory {
  constructor(initialPatch, limit = 20) { this.limit = Math.max(20, limit); this.past = []; this.present = clone(initialPatch); this.future = []; }
  commit(nextPatch) { this.past.push(clone(this.present)); if (this.past.length > this.limit) this.past.shift(); this.present = clone(nextPatch); this.future = []; return this.present; }
  mutate(mutator) { const next = clone(this.present); mutator(next); return this.commit(next); }
  undo() { if (!this.past.length) return this.present; this.future.push(clone(this.present)); this.present = this.past.pop(); return clone(this.present); }
  redo() { if (!this.future.length) return this.present; this.past.push(clone(this.present)); this.present = this.future.pop(); return clone(this.present); }
  reset(patch) { return this.commit(patch); }
}
