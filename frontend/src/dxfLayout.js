import { emptyFacilityLayout } from './facilityLayout.js';

export const DXF_UNIT_METERS = Object.freeze({
  millimeter: .001, centimeter: .01, meter: 1, inch: .0254, foot: .3048,
});
const HEADER_UNITS = { 1: 'inch', 2: 'foot', 4: 'millimeter', 5: 'centimeter', 6: 'meter' };

export function parseAsciiDxf(source) {
  if (typeof source !== 'string' || !source.includes('SECTION')) throw new Error('Ожидается текстовый DXF из AutoCAD. DWG нужно экспортировать в DXF.');
  const lines = source.replace(/\r/g, '').split('\n');
  const pairs = [];
  for (let index = 0; index + 1 < lines.length; index += 2) {
    const code = Number(lines[index].trim());
    if (Number.isInteger(code)) pairs.push([code, lines[index + 1].trim()]);
  }
  let section = '', unit = null, current = null, unsupported = 0, malformed = 0;
  const segments = [];
  const pushCurrent = () => {
    if (!current) return;
    const { type, values, vertices, layer } = current;
    if (type === 'LINE') {
      const [x1, y1, x2, y2] = [values[10], values[20], values[11], values[21]].map(Number);
      if ([x1, y1, x2, y2].every(Number.isFinite)) segments.push({ layer, x1, y1, x2, y2 });
      else malformed++;
    } else if (type === 'LWPOLYLINE' && vertices.length >= 2) {
      const points = vertices.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
      if (points.length !== vertices.length || points.length < 2) malformed++;
      for (let index = 1; index < points.length; index++) segments.push({ layer, x1: points[index - 1].x, y1: points[index - 1].y, x2: points[index].x, y2: points[index].y });
      if (Number(values[70] || 0) & 1) segments.push({ layer, x1: points.at(-1).x, y1: points.at(-1).y, x2: points[0].x, y2: points[0].y });
    } else if (type === 'LWPOLYLINE') malformed++;
    else unsupported++;
    current = null;
  };
  for (let index = 0; index < pairs.length; index++) {
    const [code, value] = pairs[index];
    if (code === 0 && value === 'SECTION') { pushCurrent(); section = pairs[index + 1]?.[1] || ''; continue; }
    if (code === 0 && value === 'ENDSEC') { pushCurrent(); section = ''; continue; }
    if (section === 'HEADER' && code === 9 && value === '$INSUNITS')
      unit = HEADER_UNITS[Number(pairs[index + 1]?.[1])] || null;
    if (section !== 'ENTITIES') continue;
    if (code === 0) { pushCurrent(); current = { type: value, layer: '0', values: {}, vertices: [] }; continue; }
    if (!current) continue;
    if (code === 8) current.layer = value || '0';
    else if (current.type === 'LWPOLYLINE' && code === 10) current.vertices.push({ x: Number(value), y: NaN });
    else if (current.type === 'LWPOLYLINE' && code === 20 && current.vertices.length) current.vertices.at(-1).y = Number(value);
    else if ([10, 11, 20, 21, 70].includes(code)) current.values[code] = value;
  }
  pushCurrent();
  if (!segments.length) throw new Error('В DXF не найдены отрезки LINE или LWPOLYLINE. Проверьте экспорт слоя с планом.');
  return { schema_version: 'dxf-layout-import-v1', unit, segments,
    layers: [...new Set(segments.map((line) => line.layer))].sort(), unsupported_entities: unsupported,
    malformed_entities: malformed };
}

export function dxfToFacilityLayout(parsed, { unit, layers, wallThicknessM = .2, sourceName = 'plan.dxf' }) {
  const factor = DXF_UNIT_METERS[unit];
  if (!factor) throw new Error('Выберите единицы чертежа перед импортом.');
  const chosen = parsed.segments.filter((line) => layers.includes(line.layer));
  if (!chosen.length) throw new Error('Выберите слой с линиями стен или препятствий.');
  if (chosen.length > 300) throw new Error('На выбранных слоях больше 300 отрезков. Выделите только стены и крупные препятствия.');
  const xs = chosen.flatMap((line) => [line.x1, line.x2]), ys = chosen.flatMap((line) => [line.y1, line.y2]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = (maxX - minX) * factor + 4, depth = (maxY - minY) * factor + 4;
  if (width < 10 || depth < 10 || width > 500 || depth > 500)
    throw new Error('Получились размеры вне диапазона 10–500 м. Проверьте единицы и слои DXF.');
  const items = [], skipped = [];
  chosen.forEach((line, index) => {
    const x1 = (line.x1 - minX) * factor + 2, x2 = (line.x2 - minX) * factor + 2;
    const y1 = (line.y1 - minY) * factor + 2, y2 = (line.y2 - minY) * factor + 2;
    const dx = Math.abs(x2 - x1), dy = Math.abs(y2 - y1);
    if (Math.min(dx, dy) > Math.max(.02, Math.max(dx, dy) * .01)) { skipped.push(index + 1); return; }
    const horizontal = dx >= dy;
    const thickness = Math.max(.05, Math.min(2, Number(wallThicknessM) || .2));
    items.push({ id: `dxf-${index}`, kind: 'obstacle',
      x: Math.max(0, Math.min(x1, x2) - (horizontal ? 0 : thickness / 2)),
      y: Math.max(0, Math.min(y1, y2) - (horizontal ? thickness / 2 : 0)),
      width_m: Math.max(thickness, dx), depth_m: Math.max(thickness, dy),
      provenance: 'PROVIDED', source_layer: line.layer });
  });
  if (!items.length) throw new Error('На выбранных слоях нет горизонтальных или вертикальных отрезков. Диагонали не импортируются как препятствия.');
  return { ...emptyFacilityLayout(), source: 'DXF_TRACE', width_m: Number(width.toFixed(2)), depth_m: Number(depth.toFixed(2)), items,
    cad_metadata: { format: 'ASCII_DXF', file_name: sourceName, unit, selected_layers: layers,
      imported_segments: items.length, skipped_diagonal_segments: skipped.length,
      unsupported_entities: parsed.unsupported_entities, malformed_entities: parsed.malformed_entities,
      wall_thickness_m: wallThicknessM } };
}
