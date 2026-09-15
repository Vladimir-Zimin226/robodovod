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
  const ea = solidExtents(a);
  const eb = solidExtents(b);
  const vertical = Math.abs(a.position[1] - b.position[1]) * 2 < a.scale[1] + b.scale[1] - clearance;
  return vertical && Math.abs(a.position[0] - b.position[0]) < ea.x + eb.x - clearance &&
    Math.abs(a.position[2] - b.position[2]) < ea.z + eb.z - clearance;
}

export function canPlaceSolid(candidate, solids, ignoredEditorId = null) {
  return !solids.some(solid => solid.editorId !== ignoredEditorId && solidsOverlap(candidate, solid));
}

