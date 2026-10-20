export function mapScale(width, height, sceneWidth, sceneDepth, zoom = 1) {
  return Math.min(width / (sceneWidth + 8), height / (sceneDepth + 8)) * zoom;
}

export function mapPoint(clientX, clientY, rect, width, depth, view = {}) {
  const scale = mapScale(rect.width, rect.height, width, depth, view.zoom || 1);
  return [(clientX - rect.left - rect.width / 2) / scale - (view.panX || 0),
    (clientY - rect.top - rect.height / 2) / scale - (view.panZ || 0)];
}

export function mapZoomAt(view, factor, clientX, clientY, rect, width, depth) {
  const before = mapPoint(clientX, clientY, rect, width, depth, view);
  const zoom = Math.max(.5, Math.min(4, (view.zoom || 1) * factor));
  const next = { ...view, zoom };
  const after = mapPoint(clientX, clientY, rect, width, depth, next);
  return { ...next, panX: (view.panX || 0) + after[0] - before[0],
    panZ: (view.panZ || 0) + after[1] - before[1] };
}

export function validZonePolygon(points, width, depth) {
  if (!Array.isArray(points) || points.length < 3 || points.length > 64) return false;
  if (!Number.isFinite(width) || !Number.isFinite(depth) || width <= 0 || depth <= 0) return false;
  if (points.some(point => !Array.isArray(point) || point.length !== 2 || point.some(value => !Number.isFinite(value))
    || Math.abs(point[0]) > width / 2 || Math.abs(point[1]) > depth / 2)) return false;
  const area = points.reduce((sum, point, i) => {
    const next = points[(i + 1) % points.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0);
  if (Math.abs(area) < 1) return false;
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i], b = points[(i + 1) % points.length];
    if (Math.hypot(a[0] - b[0], a[1] - b[1]) < .1) return false;
    for (let j = i + 2; j < points.length; j += 1) {
      if (i === 0 && j === points.length - 1) continue;
      const c = points[j], d = points[(j + 1) % points.length];
      if (cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0) return false;
    }
  }
  return true;
}

export function mapEntityAt(point, entities) {
  return [...entities].reverse().find(entity =>
    Math.abs(point[0] - entity.position[0]) <= entity.scale[0] / 2 &&
    Math.abs(point[1] - entity.position[2]) <= entity.scale[2] / 2
  ) || null;
}

export function drawMap(context, scene, entities, preview = null, view = {}, zoneDraft = [], wallDraft = null, roomDraft = [], anchors = [], operationalPath = [], robots = []) {
  const { width, height } = context.canvas;
  const scale = mapScale(width, height, scene.config.width, scene.config.depth, view.zoom || 1);
  context.clearRect(0, 0, width, height);
  context.fillStyle = '#0b211c'; context.fillRect(0, 0, width, height);
  context.save(); context.translate(width / 2 + (view.panX || 0) * scale, height / 2 + (view.panZ || 0) * scale); context.scale(scale, scale);
  context.fillStyle = '#3d514c'; context.fillRect(-scene.config.width / 2, -scene.config.depth / 2, scene.config.width, scene.config.depth);
  context.beginPath();
  context.lineWidth = 1 / scale; context.strokeStyle = '#c8e5d228';
  for (let x = -Math.floor(scene.config.width / 2); x <= scene.config.width / 2; x += 1) { context.moveTo(x, -scene.config.depth / 2); context.lineTo(x, scene.config.depth / 2); }
  for (let z = -Math.floor(scene.config.depth / 2); z <= scene.config.depth / 2; z += 1) { context.moveTo(-scene.config.width / 2, z); context.lineTo(scene.config.width / 2, z); }
  context.stroke();
  const paintRoom = (points, draft = false, doors = []) => {
    if (!points.length) return;
    context.beginPath(); context.moveTo(points[0][0], points[0][1]);
    points.slice(1).forEach(point => context.lineTo(point[0], point[1]));
    if (!draft) context.closePath();
    context.fillStyle = '#d5c08e4d'; context.strokeStyle = draft ? '#ffe08a' : '#d5c08e'; context.lineWidth = 2 / scale;
    if (!draft) context.fill();
    if (draft) context.stroke();
    else points.forEach((start, edge) => {
      const end = points[(edge + 1) % points.length];
      const length = Math.hypot(end[0] - start[0], end[1] - start[1]);
      const door = doors.some(item => item.edge === edge);
      const segment = (a, b) => { context.beginPath(); context.moveTo(a[0], a[1]); context.lineTo(b[0], b[1]); context.stroke(); };
      if (!door || length <= 1.2) { segment(start, end); return; }
      const interpolate = fraction => [start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction];
      segment(start, interpolate(.5 - .6 / length));
      segment(interpolate(.5 + .6 / length), end);
    });
    for (const point of points) { context.beginPath(); context.arc(point[0], point[1], 3 / scale, 0, Math.PI * 2); context.fillStyle = draft ? '#ffe08a' : '#d5c08e'; context.fill(); }
  };
  for (const room of scene.editorRooms || []) paintRoom(room.points, false, room.doors || []);
  paintRoom(roomDraft, true);
  const paintZone = (points, draft = false) => {
    if (!points.length) return;
    context.beginPath(); context.moveTo(points[0][0], points[0][1]);
    points.slice(1).forEach(point => context.lineTo(point[0], point[1]));
    if (!draft) context.closePath();
    context.fillStyle = '#43dca42e'; context.strokeStyle = draft ? '#ffcf69' : '#43dca4'; context.lineWidth = 2 / scale;
    if (!draft) context.fill();
    context.stroke();
    for (const point of points) { context.beginPath(); context.arc(point[0], point[1], 3 / scale, 0, Math.PI * 2); context.fillStyle = draft ? '#ffcf69' : '#43dca4'; context.fill(); }
  };
  for (const zone of scene.editorZones || []) paintZone(zone.points);
  paintZone(zoneDraft, true);
  if (wallDraft?.start) {
    const { start, end = start, door, valid } = wallDraft;
    context.strokeStyle = valid ? '#64f0aa' : '#ff7777'; context.lineWidth = .3;
    const line = (a, b) => { context.beginPath(); context.moveTo(a[0], a[1]); context.lineTo(b[0], b[1]); context.stroke(); };
    const dx = end[0] - start[0], dz = end[1] - start[1], length = Math.hypot(dx, dz);
    if (door && length > 1.2) {
      const left = [(start[0] + end[0]) / 2 - dx / length * .6, (start[1] + end[1]) / 2 - dz / length * .6];
      const right = [(start[0] + end[0]) / 2 + dx / length * .6, (start[1] + end[1]) / 2 + dz / length * .6];
      line(start, left); line(right, end);
    } else line(start, end);
    context.beginPath(); context.arc(start[0], start[1], .23, 0, Math.PI * 2);
    context.fillStyle = '#ffe08a'; context.fill();
  }
  const paint = (entity, color) => {
    context.save(); context.translate(entity.position[0], entity.position[2]); context.rotate(-(entity.yaw || 0));
    context.fillStyle = color;
    if (entity.kind === 'door_frame') {
      for (const side of [-1, 1]) context.fillRect(side * entity.scale[0] / 2 - .06, -entity.scale[2] / 2, .12, entity.scale[2]);
    } else context.fillRect(-entity.scale[0] / 2, -entity.scale[2] / 2, entity.scale[0], entity.scale[2]);
    context.restore();
  };
  for (const entity of entities) if (!entity.parts?.[0]?.runtimeHidden) paint(entity, entity.id.startsWith('user:') ? '#5de0a7' : '#9bb1aa');
  if (preview) paint(preview, preview.valid ? '#8af0b577' : '#ff686877');
  if (operationalPath.length > 1) {
    context.beginPath(); context.moveTo(operationalPath[0][0], operationalPath[0][1]);
    operationalPath.slice(1).forEach(point => context.lineTo(point[0], point[1]));
    context.strokeStyle = '#78c8ff'; context.lineWidth = 3 / scale; context.stroke();
  }
  for (const anchor of anchors) {
    context.beginPath(); context.arc(anchor.position[0], anchor.position[1], 5 / scale, 0, Math.PI * 2);
    context.fillStyle = anchor.role === 'CHARGE' ? '#62e6ae' : anchor.role === 'WORK' ? '#ffe08a' : '#ff9e7d'; context.fill();
    context.fillStyle = '#081c18'; context.font = `${8 / scale}px sans-serif`; context.textAlign = 'center'; context.textBaseline = 'middle';
    context.fillText(anchor.role[0], anchor.position[0], anchor.position[1]);
  }
  for (const robot of robots) {
    context.beginPath(); context.arc(robot.position[0], robot.position[2], robot.radius || .6, 0, Math.PI * 2);
    context.fillStyle = '#38caff'; context.fill(); context.strokeStyle = '#082530'; context.lineWidth = .08; context.stroke();
  }
  context.restore();
  context.fillStyle = '#e1fff0'; context.font = '12px sans-serif';
  const bar = 5 * scale;
  context.strokeStyle = '#e1fff0'; context.lineWidth = 2;
  context.beginPath(); context.moveTo(24, height - 25); context.lineTo(24 + bar, height - 25); context.stroke();
  context.fillText('5 м', 24, height - 30);
}
