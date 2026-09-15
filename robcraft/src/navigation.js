import { circleIntersectsSolid } from './editor/collisions.js';

const key = (x, z) => `${x}:${z}`;

function reconstruct(nodes, currentKey, origin, step) {
  const points = [];
  let cursor = currentKey;
  while (cursor) {
    const node = nodes.get(cursor);
    points.push([origin[0] + node.x * step, origin[1] + node.z * step]);
    cursor = node.parent;
  }
  return points.reverse();
}

function segmentClear(a, b, blocked, step) {
  const distance = Math.hypot(b[0] - a[0], b[1] - a[1]);
  for (let travelled = step * .45; travelled < distance; travelled += step * .45) {
    const amount = travelled / distance;
    if (blocked(a[0] + (b[0] - a[0]) * amount, a[1] + (b[1] - a[1]) * amount)) return false;
  }
  return true;
}

function simplify(points, blocked, step) {
  if (points.length < 3) return points;
  const result = [points[0]];
  let anchor = 0;
  while (anchor < points.length - 1) {
    let next = points.length - 1;
    while (next > anchor + 1 && !segmentClear(points[anchor], points[next], blocked, step)) next -= 1;
    result.push(points[next]);
    anchor = next;
  }
  return result;
}

export function planGridPath(start, goal, options = {}) {
  const step = options.step || .72;
  const radius = options.radius || .6;
  const solids = options.solids || [];
  const dynamic = options.dynamic || [];
  const bounds = options.bounds || { minX: Math.min(start[0], goal[0]) - 8, maxX: Math.max(start[0], goal[0]) + 8, minZ: Math.min(start[1], goal[1]) - 8, maxZ: Math.max(start[1], goal[1]) + 8 };
  const origin = [bounds.minX, bounds.minZ];
  const toCell = point => [Math.round((point[0] - origin[0]) / step), Math.round((point[1] - origin[1]) / step)];
  const toWorld = (x, z) => [origin[0] + x * step, origin[1] + z * step];
  const [startX, startZ] = toCell(start);
  const [goalX, goalZ] = toCell(goal);
  const maxCellX = Math.floor((bounds.maxX - origin[0]) / step);
  const maxCellZ = Math.floor((bounds.maxZ - origin[1]) / step);
  const blocked = (x, z, allowEndpoints = false) => {
    if (x < bounds.minX || x > bounds.maxX || z < bounds.minZ || z > bounds.maxZ) return true;
    // The exact start can already touch a newly appeared obstacle. Only exempt
    // that tiny start footprint: exempting a whole grid cell let the first
    // simplified segment cut back through the obstacle and trapped the robot.
    if (allowEndpoints && (Math.hypot(x - start[0], z - start[1]) < step * .08 || Math.hypot(x - goal[0], z - goal[1]) < step * .18)) return false;
    if (solids.some(solid => circleIntersectsSolid(x, z, radius + .10, solid))) return true;
    return dynamic.some(obstacle => Math.hypot(x - obstacle.position[0], z - obstacle.position[2]) < radius + (obstacle.radius || .6) + .24);
  };
  const startKey = key(startX, startZ);
  const nodes = new Map([[startKey, { x: startX, z: startZ, g: 0, f: Math.hypot(goalX - startX, goalZ - startZ), parent: null }]]);
  const open = new Set([startKey]);
  const closed = new Set();
  const directions = [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]];
  let iterations = 0;
  while (open.size && iterations < (options.maxIterations || 7000)) {
    iterations += 1;
    let currentKey = null;
    for (const candidate of open) {
      const node = nodes.get(candidate);
      if (!currentKey || node.f < nodes.get(currentKey).f || (node.f === nodes.get(currentKey).f && candidate < currentKey)) currentKey = candidate;
    }
    const current = nodes.get(currentKey);
    if (Math.hypot(current.x - goalX, current.z - goalZ) <= 1) {
      const raw = reconstruct(nodes, currentKey, origin, step);
      raw[0] = [...start]; raw.push([...goal]);
      return simplify(raw, (x, z) => blocked(x, z, true), step).slice(1);
    }
    open.delete(currentKey); closed.add(currentKey);
    for (const [dx, dz] of directions) {
      const x = current.x + dx; const z = current.z + dz; const nextKey = key(x, z);
      if (x < 0 || z < 0 || x > maxCellX || z > maxCellZ || closed.has(nextKey)) continue;
      const world = toWorld(x, z);
      if (blocked(world[0], world[1], true)) continue;
      if (dx && dz) {
        const sideA = toWorld(current.x + dx, current.z); const sideB = toWorld(current.x, current.z + dz);
        if (blocked(sideA[0], sideA[1], true) || blocked(sideB[0], sideB[1], true)) continue;
      }
      const g = current.g + (dx && dz ? Math.SQRT2 : 1);
      const known = nodes.get(nextKey);
      if (known && g >= known.g) continue;
      const h = Math.hypot(goalX - x, goalZ - z);
      nodes.set(nextKey, { x, z, g, f: g + h, parent: currentKey });
      open.add(nextKey);
    }
  }
  return null;
}
