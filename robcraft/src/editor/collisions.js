export function solidExtents(solid) {
  const yaw = solid.yaw || 0;
  const cosine = Math.abs(Math.cos(yaw));
  const sine = Math.abs(Math.sin(yaw));
  return {
    x: (solid.scale[0] * cosine + solid.scale[2] * sine) / 2,
    z: (solid.scale[0] * sine + solid.scale[2] * cosine) / 2
  };
}

export function circleIntersectsSolid(x, z, radius, solid) {
  const dx = x - solid.position[0];
  const dz = z - solid.position[2];
  const yaw = -(solid.yaw || 0);
  const localX = dx * Math.cos(yaw) - dz * Math.sin(yaw);
  const localZ = dx * Math.sin(yaw) + dz * Math.cos(yaw);
  const closestX = Math.max(-solid.scale[0] / 2, Math.min(solid.scale[0] / 2, localX));
  const closestZ = Math.max(-solid.scale[2] / 2, Math.min(solid.scale[2] / 2, localZ));
  return Math.hypot(localX - closestX, localZ - closestZ) < radius;
}

export function solidsOverlap(a, b, clearance = .02) {
  const vertical = Math.abs(a.position[1] - b.position[1]) * 2 < a.scale[1] + b.scale[1] - clearance;
  if (!vertical) return false;
  const axes = solid => {
    const yaw = solid.yaw || 0;
    return [[Math.cos(yaw), -Math.sin(yaw)], [Math.sin(yaw), Math.cos(yaw)]];
  };
  const aAxes = axes(a), bAxes = axes(b);
  const offset = [b.position[0] - a.position[0], b.position[2] - a.position[2]];
  const dot = (u, v) => u[0] * v[0] + u[1] * v[1];
  const radius = (solid, localAxes, axis) =>
    solid.scale[0] / 2 * Math.abs(dot(localAxes[0], axis)) +
    solid.scale[2] / 2 * Math.abs(dot(localAxes[1], axis));
  return [...aAxes, ...bAxes].every(axis =>
    Math.abs(dot(offset, axis)) < radius(a, aAxes, axis) + radius(b, bAxes, axis) - clearance);
}

export function canPlaceSolid(candidate, solids, ignoredEditorId = null) {
  return !solids.some(solid => solid.editorId !== ignoredEditorId && solidsOverlap(candidate, solid));
}

