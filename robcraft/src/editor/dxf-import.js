// RobCraft subset of the existing frontend/src/dxfLayout.js ASCII DXF reader.
// Only straight LINE/LWPOLYLINE geometry is promoted to collision geometry.
const UNIT_METERS = { 1: .0254, 2: .3048, 4: .001, 5: .01, 6: 1 };

export function parseRobcraftDxf(source, options = {}) {
  if (typeof source !== 'string' || source.length > 5_000_000 || !source.includes('SECTION')) throw new Error('Нужен текстовый DXF до 5 МБ. DWG экспортируйте в DXF.');
  const lines = source.replace(/\r/g, '').split('\n');
  const pairs = [];
  for (let i = 0; i + 1 < lines.length; i += 2) {
    const code = Number(lines[i].trim());
    if (Number.isInteger(code)) pairs.push([code, lines[i + 1].trim()]);
  }
  let section = '', unit = null, entity = null, unsupported = 0, malformed = 0;
  const segments = [];
  const finish = () => {
    if (!entity) return;
    const { type, values, vertices, layer, curved } = entity;
    if (curved) unsupported += 1;
    else if (type === 'LINE') {
      const coords = [10, 20, 11, 21].map(code => Number(values[code]));
      if (coords.every(Number.isFinite)) segments.push({ layer, points: [[coords[0], coords[1]], [coords[2], coords[3]]] });
      else malformed += 1;
    } else if (type === 'LWPOLYLINE') {
      if (vertices.length < 2 || vertices.some(point => !point.every(Number.isFinite))) malformed += 1;
      else {
        for (let j = 1; j < vertices.length; j += 1) segments.push({ layer, points: [vertices[j - 1], vertices[j]] });
        if (Number(values[70] || 0) & 1) segments.push({ layer, points: [vertices.at(-1), vertices[0]] });
      }
    } else unsupported += 1;
    entity = null;
  };
  for (let i = 0; i < pairs.length; i += 1) {
    const [code, value] = pairs[i];
    if (code === 0 && value === 'SECTION') { finish(); section = pairs[i + 1]?.[1] || ''; continue; }
    if (code === 0 && value === 'ENDSEC') { finish(); section = ''; continue; }
    if (section === 'HEADER' && code === 9 && value === '$INSUNITS') unit = UNIT_METERS[Number(pairs[i + 1]?.[1])] || null;
    if (section !== 'ENTITIES') continue;
    if (code === 0) { finish(); entity = { type: value, layer: '0', values: {}, vertices: [], curved: false }; continue; }
    if (!entity) continue;
    if (code === 8) entity.layer = value || '0';
    else if (entity.type === 'LWPOLYLINE' && code === 10) entity.vertices.push([Number(value), NaN]);
    else if (entity.type === 'LWPOLYLINE' && code === 20 && entity.vertices.length) entity.vertices.at(-1)[1] = Number(value);
    else if (code === 42 && Number(value) !== 0) entity.curved = true;
    else if ([10, 11, 20, 21, 70].includes(code)) entity.values[code] = value;
  }
  finish();
  const factor = options.unitMeters || unit;
  if (!Number.isFinite(factor) || factor <= 0) throw new Error('Не определены единицы DXF. Укажите масштаб в метрах на единицу.');
  const wallLayers = new Set(options.wallLayers || []), obstacleLayers = new Set(options.obstacleLayers || []);
  const selected = segments.filter(segment => wallLayers.has(segment.layer) || obstacleLayers.has(segment.layer));
  if (!selected.length) throw new Error('На выбранных слоях нет поддержанных LINE/LWPOLYLINE.');
  if (selected.length > 300) throw new Error('На выбранных слоях более 300 прямых сегментов.');
  const coords = selected.flatMap(item => item.points), xs = coords.map(point => point[0]), zs = coords.map(point => point[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const width = (maxX - minX) * factor + 4, depth = (maxZ - minZ) * factor + 4;
  if (width < 10 || depth < 10 || width > 80 || depth > 70) throw new Error('Размеры DXF вне 10–80 × 10–70 м. Проверьте масштаб и слои.');
  const height = Number(options.wallHeightM);
  if (!Number.isFinite(height) || height < 1 || height > 12) throw new Error('Укажите высоту стен от 1 до 12 м.');
  const objects = selected.map(segment => {
    const [[ax, az], [bx, bz]] = segment.points.map(([x, z]) => [(x - minX) * factor - width / 2 + 2, (z - minZ) * factor - depth / 2 + 2]);
    const length = Math.hypot(bx - ax, bz - az);
    if (length < .1) return null;
    const wall = wallLayers.has(segment.layer);
    return { kind: wall ? 'wall' : 'rack', type: wall ? 'wall' : 'rack', position: [(ax + bx) / 2, wall ? height / 2 : .75, (az + bz) / 2],
      scale: [length, wall ? height : 1.5, wall ? .2 : .8], yaw: -Math.atan2(bz - az, bx - ax),
      color: wall ? [.73, .78, .75] : [.3, .44, .44], meta: { label: `${wall ? 'Стена' : 'Препятствие'} · ${segment.layer}` }, solid: true };
  }).filter(Boolean);
  if (!objects.length) throw new Error('На выбранных слоях нет сегментов длиной от 0,1 м.');
  return { width, depth, objects, unitMeters: factor, layers: [...new Set(segments.map(item => item.layer))],
    wallHeightM: height, wallLayers: [...wallLayers], obstacleLayers: [...obstacleLayers],
    unsupported, malformed, skippedLayers: [...new Set(segments.map(item => item.layer))].filter(layer => !wallLayers.has(layer) && !obstacleLayers.has(layer)) };
}
