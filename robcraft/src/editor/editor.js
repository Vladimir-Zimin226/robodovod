import { canPlaceSolid } from './collisions.js';
import { applyScenePatch, compatibleRobotTypes, createScenePatch, listEditableEntities, SceneHistory } from './scene-patch.js';

export const BUILD_CATALOG = Object.freeze([
  { kind: 'wall', label: 'Стена', scale: [4, 3, .3], color: [.73, .78, .75] },
  { kind: 'rack', label: 'Стеллаж', scale: [2.5, 4.7, 1.25], color: [.18, .25, .25] },
  { kind: 'cargo', label: 'Паллета / груз', scale: [1.2, .8, 1], color: [.64, .42, .20] },
  { kind: 'station', label: 'Рабочая станция', scale: [3, 1, 1.8], color: [.95, .72, .10] },
  { kind: 'charger', label: 'Зарядная позиция', scale: [1, .16, 1.2], color: [.12, .75, .48], solid: false },
  { kind: 'fence', label: 'Ограждение', scale: [3, 1.2, .16], color: [.92, .48, .12] },
  { kind: 'decor', label: 'Декоративный блок', scale: [1, 1, 1], color: [.30, .55, .48] }
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
    let sequence = (this.history.present.created?.length || 0) + 1;
    while (this.history.present.created.some(item => item.id === `user:${kind}:${sequence}`)) sequence += 1;
    const id = `user:${kind}:${sequence}`;
    const object = { id, kind, editorId: id, editorKind: kind, type: kind, position: [...position], scale: [...preset.scale], yaw: options.yaw || 0, color: [...preset.color], meta: { label: preset.label }, solid: preset.solid !== false };
    const collider = { position: object.position, scale: object.scale, yaw: object.yaw, editorId: id };
    if (object.solid && !canPlaceSolid(collider, this.scene.solids)) return null;
    this.history.mutate(patch => patch.created.push(object)); this.selectedId = id; this.refresh(); return id;
  }

  delete(id = this.selectedId) {
    if (!this.entity(id)) return false;
    this.history.mutate(patch => {
      const index = patch.created.findIndex(item => item.id === id);
      if (index >= 0) patch.created.splice(index, 1);
      else if (!patch.deleted.includes(id)) patch.deleted.push(id);
      delete patch.objects[id];
    });
    if (this.selectedId === id) this.selectedId = null;
    this.refresh(); return true;
  }

  duplicate(id = this.selectedId, offset = [1, 0, 1]) {
    const entity = this.entity(id); if (!entity) return null;
    const preset = BUILD_CATALOG.find(item => item.kind === entity.kind) || BUILD_CATALOG.at(-1);
    let sequence = (this.history.present.created?.length || 0) + 1;
    let createdId = `user:${entity.kind}:${sequence}`;
    while (this.history.present.created.some(item => item.id === createdId)) createdId = `user:${entity.kind}:${++sequence}`;
    const object = { id: createdId, kind: entity.kind, editorId: createdId, editorKind: entity.kind, type: entity.kind, position: entity.position.map((value, axis) => value + offset[axis]), scale: [...entity.scale], yaw: entity.yaw, color: [...(entity.parts[0].color || preset.color)], meta: { label: `${entity.label} (копия)` }, solid: preset.solid !== false };
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
  const distance = Math.min(maxDistance, Math.max(0, -.02 / ray.direction[1]));
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
