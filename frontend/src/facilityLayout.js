// A local, explicitly approximate route check for an authored warehouse layout.
// The server receives a distance only after the user applies it to an intake field.
export const FACILITY_LAYOUT_VERSION = 'facility-layout-v1';

export const ITEM_SIZES = Object.freeze({
  rack: [5, 2], obstacle: [3, 3], no_go: [4, 4], aisle: [6, 2],
  charger: [1.5, 1.5], pickup: [1, 1], dropoff: [1, 1],
  receiving: [10, 8], picking: [10, 8], packing: [10, 8],
  shipping: [10, 8], staging: [8, 6],
});

export function emptyFacilityLayout() {
  return { schema_version: FACILITY_LAYOUT_VERSION, source: 'DRAWN', width_m: 60,
    depth_m: 36, imageData: null, zones: [], items: [] };
}

export function exampleFacilityLayout() {
  const assumed = (id, kind, x, y, width_m, depth_m) =>
    ({ id, kind, x, y, width_m, depth_m, provenance: 'ASSUMED' });
  return { ...emptyFacilityLayout(), source: 'ASSUMED_REFERENCE', width_m: 72, depth_m: 48,
    robot_width_m: 1, reference_note: 'Авторская учебная U-образная схема по открытым материалам; размеры и объёмы не принадлежат реальному складу.',
    items: [
      assumed('receiving', 'receiving', 2, 3, 11, 8),
      assumed('picking', 'picking', 2, 35, 11, 9),
      assumed('packing', 'packing', 57, 35, 12, 9),
      assumed('shipping', 'shipping', 58, 3, 11, 9),
      assumed('staging-in', 'staging', 14, 4, 4, 6),
      assumed('staging-out', 'staging', 53, 4, 4, 6),
      ...[19, 31, 43].flatMap((x, column) => [5, 14, 34, 43].map((y, row) =>
        assumed(`rack-${column + 1}-${row + 1}`, 'rack', x, y, 7, 2))),
      assumed('charger', 'charger', 54, 42, 2, 2),
      assumed('island', 'obstacle', 42, 22, 4, 5),
      assumed('pickup', 'pickup', 17, 23, 1, 1),
      assumed('dropoff', 'dropoff', 63, 23, 1, 1),
    ] };
}

export function layoutFingerprint(layout) {
  return JSON.stringify([layout.width_m, layout.depth_m, layout.robot_width_m, (layout.items || []).map((item) =>
    [item.kind, item.x, item.y, item.width_m, item.depth_m, item.provenance])]);
}

export function itemSize(item) {
  return [Number(item.width_m) || ITEM_SIZES[item.kind]?.[0] || 1,
    Number(item.depth_m) || ITEM_SIZES[item.kind]?.[1] || 1];
}

export function parseFacilityLayoutDraft(raw) {
  if (typeof raw !== 'string' || raw.length > 256_000) throw new Error('Файл схемы слишком большой.');
  let value;
  try { value = JSON.parse(raw); } catch { throw new Error('Это не JSON-файл схемы.'); }
  if (!value || value.schema_version !== FACILITY_LAYOUT_VERSION || !Array.isArray(value.items)
      || value.items.length > 400) throw new Error('Нужна схема facility-layout-v1 с не более чем 400 объектами.');
  const width = Number(value.width_m), depth = Number(value.depth_m);
  const robotWidth = Number(value.robot_width_m || 1);
  if (![width, depth, robotWidth].every(Number.isFinite) || width < 10 || width > 500
      || depth < 10 || depth > 500 || robotWidth < .5 || robotWidth > 3) throw new Error('Проверьте размеры схемы и робота.');
  const items = value.items.map((item, index) => {
    if (!item || !Object.hasOwn(ITEM_SIZES, item.kind)) throw new Error(`Неподдерживаемый объект ${index + 1}.`);
    const [w, h] = itemSize(item), x = Number(item.x), y = Number(item.y);
    if (![w, h, x, y].every(Number.isFinite) || x < 0 || y < 0 || w < .5 || h < .5
        || x + w > width || y + h > depth) throw new Error(`Объект ${index + 1} выходит за пределы схемы.`);
    return { id: typeof item.id === 'string' && item.id.length <= 100 ? item.id : `imported-${index}`,
      kind: item.kind, x, y, width_m: w, depth_m: h,
      provenance: ['ASSUMED', 'PROVIDED', 'DRAWN'].includes(item.provenance) ? item.provenance : 'DRAWN' };
  });
  return { ...emptyFacilityLayout(), source: 'JSON_DRAFT', width_m: width, depth_m: depth,
    robot_width_m: robotWidth, items, reference_note: typeof value.reference_note === 'string'
      ? value.reference_note.slice(0, 500) : undefined };
}

const BLOCKS_ROUTE = new Set(['rack', 'obstacle', 'no_go', 'charger']);
const center = (item) => {
  const [width, depth] = itemSize(item);
  return { x: Number(item.x) + width / 2, y: Number(item.y) + depth / 2 };
};

class MinHeap {
  constructor() { this.values = []; }
  push(item) {
    const values = this.values;
    let index = values.length;
    values.push(item);
    while (index) {
      const parent = (index - 1) >> 1;
      if (values[parent].score <= item.score) break;
      values[index] = values[parent]; index = parent;
    }
    values[index] = item;
  }
  pop() {
    const values = this.values;
    const top = values[0], last = values.pop();
    if (values.length) {
      let index = 0;
      while (index * 2 + 1 < values.length) {
        let child = index * 2 + 1;
        if (child + 1 < values.length && values[child + 1].score < values[child].score) child++;
        if (last.score <= values[child].score) break;
        values[index] = values[child]; index = child;
      }
      values[index] = last;
    }
    return top;
  }
  get size() { return this.values.length; }
}

export function estimateFacilityRoute(layout, { robotWidthM = 1, clearanceM = .25 } = {}) {
  const width = Number(layout?.width_m), depth = Number(layout?.depth_m);
  if (!Number.isFinite(width) || !Number.isFinite(depth) || width < 3 || depth < 3 || width > 500 || depth > 500)
    return { status: 'INVALID', reason: 'Проверьте размеры помещения: от 3 до 500 м.' };
  const items = layout.items || [];
  if (items.some((item) => {
    const [w, h] = itemSize(item), x = Number(item.x), y = Number(item.y);
    return !Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)
      || x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > width || y + h > depth;
  })) return { status: 'INVALID', reason: 'Один из объектов выходит за границы помещения. Исправьте размеры или положение.' };
  const pickup = items.find((item) => item.kind === 'pickup');
  const dropoff = items.find((item) => item.kind === 'dropoff');
  if (!pickup || !dropoff) return { status: 'NEEDS_ENDPOINTS', reason: 'Поставьте точки приёмки и отгрузки.' };
  const step = Math.max(.5, width / 160, depth / 160);
  const cols = Math.ceil(width / step), rows = Math.ceil(depth / step);
  const radius = robotWidthM / 2 + clearanceM;
  const fixtures = items.filter((item) => BLOCKS_ROUTE.has(item.kind)).map((item) => {
    const [w, h] = itemSize(item);
    return { x: Number(item.x), y: Number(item.y), w, h };
  });
  const pointAt = (col, row) => ({ x: Math.min(width, (col + .5) * step), y: Math.min(depth, (row + .5) * step) });
  const passable = (col, row) => {
    if (col < 0 || row < 0 || col >= cols || row >= rows) return false;
    const { x, y } = pointAt(col, row);
    return x >= radius && x <= width - radius && y >= radius && y <= depth - radius
      && fixtures.every((item) => x < item.x - radius || x > item.x + item.w + radius
        || y < item.y - radius || y > item.y + item.h + radius);
  };
  const cellFor = (item) => {
    const point = center(item);
    return { col: Math.min(cols - 1, Math.floor(point.x / step)),
      row: Math.min(rows - 1, Math.floor(point.y / step)) };
  };
  const start = cellFor(pickup), end = cellFor(dropoff);
  if (start.col === end.col && start.row === end.row)
    return { status: 'INVALID', reason: 'Разнесите точки приёмки и отгрузки.' };
  if (!passable(start.col, start.row) || !passable(end.col, end.row))
    return { status: 'BLOCKED', reason: 'Точка передачи слишком близко к препятствию или стене для заданного габарита.', step_m: step };
  const startId = start.row * cols + start.col, endId = end.row * cols + end.col;
  const cost = new Float64Array(cols * rows).fill(Infinity);
  const parent = new Int32Array(cols * rows).fill(-1);
  const heap = new MinHeap();
  const heuristic = (col, row) => Math.abs(col - end.col) + Math.abs(row - end.row);
  cost[startId] = 0;
  heap.push({ id: startId, score: heuristic(start.col, start.row), travel: 0 });
  while (heap.size) {
    const current = heap.pop();
    if (current.travel !== cost[current.id]) continue;
    if (current.id === endId) break;
    const col = current.id % cols, row = Math.floor(current.id / cols);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = col + dx, ny = row + dy;
      if (!passable(nx, ny)) continue;
      const next = ny * cols + nx, travel = current.travel + 1;
      if (travel >= cost[next]) continue;
      cost[next] = travel; parent[next] = current.id;
      heap.push({ id: next, score: travel + heuristic(nx, ny), travel });
    }
  }
  if (!Number.isFinite(cost[endId]))
    return { status: 'BLOCKED', reason: 'Проходимого маршрута между точками нет. Проверьте запретные зоны и габарит робота.', step_m: step };
  const cells = [];
  for (let id = endId; id !== -1; id = parent[id]) cells.push(pointAt(id % cols, Math.floor(id / cols)));
  cells.reverse();
  const straight_m = Math.hypot(center(pickup).x - center(dropoff).x, center(pickup).y - center(dropoff).y);
  return { status: 'READY', length_m: Number((cost[endId] * step).toFixed(1)),
    straight_m: Number(straight_m.toFixed(1)), path: cells, step_m: step,
    robot_width_m: robotWidthM, clearance_m: clearanceM };
}
