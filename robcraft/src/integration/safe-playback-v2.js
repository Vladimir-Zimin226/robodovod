// A separate, read-only presentation. Historical v1 captures and server KPIs stay versioned.
import policy from './live-playback-v2.json' with { type: 'json' };
import { pointAlong } from './facility-playback.js';

export const LIVE_PLAYBACK_VERSION = policy.version;
export const LIVE_TIME_SCALE = policy.model_seconds_per_view_second;
export const VISUAL_FOOTPRINT = Object.freeze({ width: policy.robot_body_width_m, length: policy.robot_body_length_m,
  radius: Math.hypot(policy.robot_body_width_m / 2, policy.robot_body_length_m / 2), clearance: policy.clearance_m });
export const STAGE_LABELS = Object.freeze({ TO_LOAD: 'К точке приёма', LOAD: 'Приём груза', OUTBOUND: 'Доставка груза',
  UNLOAD: 'Передача груза', RETURN: 'Возврат на стоянку', WORK: 'Обработка участка', TRANSIT: 'Переход к участку',
  ALLOWANCE: 'Технологическая пауза', WAITING: 'Ожидание задания', WAIT_RESOURCE: 'Ожидание безопасного маршрута или ресурса',
  OFF_SHIFT: 'Перерыв по графику', NO_PATH: 'Маршрут недоступен' });
const DAY = 86400, EPS = .001;
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const point = (x, y) => ({ x, y });
const length = (points) => points.slice(1).reduce((sum, b, i) => sum + distance(points[i], b), 0);

export function supportsSafePlayback(spec) {
  return spec?.schema_version === 'scenario-spec-v2' && ['warehouse', 'airport', 'hospital'].includes(spec.template)
    && policy.profiles.includes(spec.profile?.calculation_profile);
}

export function createSafePlan(spec, zoneId = spec.zones[0]?.zone_id) {
  if (!supportsSafePlayback(spec)) return null;
  const zone = spec.zones.find((item) => item.zone_id === zoneId);
  const task = spec.tasks.find((item) => item.zone_id === zoneId && item.process_id === spec.profile.process_id)
    || spec.tasks.find((item) => item.zone_id === zoneId);
  const fleets = spec.fleet.filter((item) => item.zone_id === zoneId && item.process_id === task?.process_id);
  if (!zone || !task || !fleets.length) return null;
  const robots = fleets.flatMap((fleet) => Array.from({ length: fleet.selected_fleet }, (_, index) => ({
    id: `${fleet.fleet_id}.${index + 1}`, fleetId: fleet.fleet_id, modelId: fleet.model_id, zoneId, taskId: task.task_id,
    routeId: task.route_ref, ordinal: 0,
  }))).map((robot, ordinal) => ({ ...robot, ordinal }));
  if (robots.length > policy.max_visual_fleet) throw new TypeError('Парк превышает предел условного представления');
  const profile = spec.profile.calculation_profile;
  const cleaning = profile === 'CLEANING_AREA_V1';
  const clinic = spec.template === 'hospital' && !cleaning;
  const stationary = profile === 'PALLETIZING_THROUGHPUT_V1';
  const width = clinic || cleaning ? Math.max(48, robots.length * 3.2 + 6) : 48;
  const height = clinic || cleaning ? 38 : Math.max(32, 10 + robots.length * policy.lane_pitch_m);
  let areas, furniture = [], walls = [], people = [];
  if (clinic) {
    areas = [{ id: 'food', label: spec.profile.process_code === 'clinic_food' ? 'Раздача питания' : 'Точка выдачи груза', x: 1, y: 28, width: width - 2, height: 9 },
      { id: 'corridor', label: 'Два направления коридора', x: 21, y: 0, width: 6, height: 28 },
      ...[0, 1, 2].flatMap((row) => [0, 1].map((side) => ({ id: `ward-${row * 2 + side + 1}`,
        label: `Отделение ${row * 2 + side + 1}`, x: side ? 27 : 0, y: row * 9, width: 21, height: 8 })))];
    furniture = areas.slice(2).flatMap((area) => [
      { type: 'bed', x: area.x + 2, y: area.y + 1, width: 3, height: 1.8 },
      { type: 'desk', x: area.x + 13, y: area.y + 1, width: 3, height: 1.8 },
    ]);
    walls = areas.slice(2).flatMap((area) => [
      { x: area.x, y: area.y + 8.5, width: 21, height: .2 },
      { x: area.x ? 27 : 21, y: area.y, width: .2, height: 2 },
      { x: area.x ? 27 : 21, y: area.y + 6, width: .2, height: 2 },
    ]);
    people = [{ x: 1.5, y: 29, radius: policy.person_radius_m, label: 'Сотрудник выдачи' }];
  } else if (cleaning) {
    const hallWidth = (width - 3) / 3;
    areas = [0, 1, 2].map((index) => ({ id: `hall-${index}`, label: `Участок уборки ${index + 1}`,
      x: index * hallWidth + 1, y: 0, width: hallWidth - 1, height: 27 }));
    areas.push({ id: 'service', label: 'Транзит и отдельные стоянки', x: 0, y: 28, width, height: 9 });
    furniture = areas.slice(0, 3).map((area) => ({ type: 'counter', x: area.x + 1, y: 2, width: 4, height: 1.5 }));
    people = areas.slice(0, 3).map((area) => ({ x: area.x + 7, y: 3, radius: policy.person_radius_m, label: 'Посетитель' }));
  } else {
    areas = [{ id: 'pickup', label: stationary ? 'Рабочие ячейки' : 'Приём груза', x: 0, y: 0, width: 9, height },
      { id: 'lanes', label: 'Раздельные направления · безопасные полосы', x: 9, y: 0, width: 30, height },
      { id: 'handoff', label: 'Передача груза', x: 39, y: 0, width: 9, height }];
    furniture = [{ type: 'rack', x: 42, y: 3, width: 3, height: Math.max(3, height - 6) }];
    people = [{ x: 40, y: 2, radius: policy.person_radius_m, label: 'Сотрудник приёмки' }];
  }
  const plan = { kind: 'FACILITY_PROCESS', presentationVersion: LIVE_PLAYBACK_VERSION, template: spec.template, profile,
    processCode: spec.profile.process_code, zoneId, label: zone.label, width, height, robots, task, fleets, fleet: fleets[0],
    areas, furniture, walls, people, cleaning, clinic, stationary, footprint: VISUAL_FOOTPRINT,
    geometrySource: zone.geometry_source, geometryRef: zone.geometry_ref, assumptionRef: zone.assumption_ref,
    route: spec.routes.find((route) => route.route_id === task.route_ref) || null };
  plan.homes = robots.map((robot) => safeRoute(plan, robot.ordinal).home);
  return plan;
}

export function safeRoute(plan, ordinal, sequence = 0) {
  if (plan.clinic) {
    const area = plan.areas[2 + sequence % 6];
    const home = point(3 + ordinal * 3.2, 35), pickup = point(23, 29), handoff = point(area.x ? 30 : 18, area.y + 4);
    return { home, pickup, handoff, areaId: area.id, areaLabel: area.label,
      toLoad: [home, point(home.x, 32), point(23, 32), pickup],
      outbound: [pickup, point(23, handoff.y), handoff], work: [handoff, handoff],
      returning: [handoff, point(25, handoff.y), point(25, 32), point(home.x, 32), home] };
  }
  if (plan.cleaning) {
    const area = plan.areas[(ordinal + Math.floor(sequence / Math.max(1, plan.robots.length))) % 3];
    const lane = Math.floor(ordinal / 3), x = area.x + 2 + lane * 3.2;
    const home = point(3 + ordinal * 3.2, 35);
    const work = [point(x, 7), point(x, 24), point(x + .45, 24), point(x + .45, 7)];
    return { home, pickup: home, handoff: work.at(-1), areaId: area.id, areaLabel: area.label, toLoad: [home, home],
      outbound: [home, point(home.x, 30), point(x, 30), work[0]], work,
      returning: [work.at(-1), point(x + .45, 30), point(home.x, 30), home] };
  }
  const y = 5 + ordinal * policy.lane_pitch_m;
  const home = point(3, y), pickup = point(6, y), handoff = point(36, y);
  return { home, pickup: plan.stationary ? home : pickup, handoff: plan.stationary ? home : handoff,
    areaId: 'lanes', areaLabel: plan.stationary ? 'Рабочая ячейка' : 'Приём → передача груза',
    toLoad: plan.stationary ? [home, home] : [home, pickup],
    outbound: plan.stationary ? [home, home] : [pickup, handoff], work: [home, home],
    returning: plan.stationary ? [home, home] : [handoff, point(36, y + 2.2), point(3, y + 2.2), home] };
}

export function visualCalendar(spec, report) {
  const origin = report.model_start?.seconds_from_midnight ?? Math.min(...spec.operating_windows.map((w) => Number(w.start_time.value)));
  const windows = spec.operating_windows.map((w) => {
    const start = (Number(w.start_time.value) - origin + DAY) % DAY;
    return [start, start + Number(w.duration.value) * 3600];
  }).sort((a, b) => a[0] - b[0]);
  // Split overnight intervals so midnight never jumps a pose or discards a shift.
  const slices = windows.flatMap(([start, end]) => end <= DAY ? [[start, end]] : [[start, DAY], [0, end - DAY]])
    .sort((a, b) => a[0] - b[0]);
  const hours = slices.reduce((sum, [a, b]) => sum + b - a, 0);
  if (hours <= 0) throw new TypeError('Нет положительного рабочего окна');
  const workAt = (time) => {
    const day = Math.floor(time / DAY), rest = time - day * DAY;
    return day * hours + slices.reduce((sum, [a, b]) => sum + Math.max(0, Math.min(rest, b) - a), 0);
  };
  const offsetAt = (work) => {
    const day = Math.floor(work / hours); let rest = work - day * hours;
    for (const [a, b] of slices) { if (rest < b - a) return day * DAY + a + rest; rest -= b - a; }
    return (day + 1) * DAY + slices[0][0];
  };
  return { hours, origin, workAt, offsetAt, isOpen: (time) => slices.some(([a, b]) => time % DAY >= a && time % DAY < b) };
}

function segmentDistance(a, b, p) {
  const dx = b.x - a.x, dy = b.y - a.y, square = dx * dx + dy * dy;
  const t = square ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / square)) : 0;
  return distance(point(a.x + t * dx, a.y + t * dy), p);
}

export function sweptHitsRectangle(a, b, rect, radius) {
  let low = 0, high = 1;
  for (const [axis, size] of [['x', 'width'], ['y', 'height']]) {
    const delta = b[axis] - a[axis], min = rect[axis] - radius, max = rect[axis] + rect[size] + radius;
    if (Math.abs(delta) < 1e-12) { if (a[axis] < min || a[axis] > max) return false; }
    else { const t1 = (min - a[axis]) / delta, t2 = (max - a[axis]) / delta;
      low = Math.max(low, Math.min(t1, t2)); high = Math.min(high, Math.max(t1, t2)); if (low > high) return false; }
  }
  return true;
}

export function sweptSeparation(left, right) {
  const start = Math.max(left.start, right.start), end = Math.min(left.end, right.end);
  if (start > end) return Infinity;
  const pose = (segment, time) => {
    const p = segment.end > segment.start ? (time - segment.start) / (segment.end - segment.start) : 0;
    return point(segment.a.x + (segment.b.x - segment.a.x) * p, segment.a.y + (segment.b.y - segment.a.y) * p);
  };
  const a = pose(left, start), b = pose(right, start), ae = pose(left, end), be = pose(right, end);
  const dx = a.x - b.x, dy = a.y - b.y, vx = ae.x - be.x - dx, vy = ae.y - be.y - dy;
  const square = vx * vx + vy * vy;
  const t = square ? Math.max(0, Math.min(1, -(dx * vx + dy * vy) / square)) : 0;
  return Math.hypot(dx + t * vx, dy + t * vy);
}

function stageSegments(stage, start, duration, points) {
  const total = length(points), output = []; let cursor = start;
  if (duration <= 0) return output;
  if (!total) return [{ stage, start, end: start + duration, a: points[0], b: points[0] }];
  for (let index = 1; index < points.length; index += 1) {
    const seconds = duration * distance(points[index - 1], points[index]) / total;
    if (seconds > 0) { output.push({ stage, start: cursor, end: cursor + seconds, a: points[index - 1], b: points[index] }); cursor += seconds; }
  }
  return output;
}

function routeIsSafe(plan, route, robot) {
  const radius = plan.footprint.radius + plan.footprint.clearance;
  for (const points of [route.toLoad, route.outbound, route.work, route.returning]) {
    for (let i = 1; i < points.length; i += 1) {
      const a = points[i - 1], b = points[i];
      if ([a, b].some((p) => p.x < radius || p.y < radius || p.x > plan.width - radius || p.y > plan.height - radius)) return false;
      if ([...plan.walls, ...plan.furniture].some((rect) => sweptHitsRectangle(a, b, rect, radius))) return false;
      if (plan.people.some((p) => segmentDistance(a, b, p) < radius + p.radius)) return false;
      if (plan.homes.some((home, other) => other !== robot && segmentDistance(a, b, home) < 2 * plan.footprint.radius + plan.footprint.clearance)) return false;
    }
  }
  return true;
}

export function createSafePlayback(plan, spec, report) {
  const calendar = visualCalendar(spec, report), byRobot = plan.robots.map(() => []), jobs = [], active = [];
  const service = Number(report.trace?.find((node) => node.output_ref === 'service.effective-seconds')?.value);
  const batch = Number(report.workload?.batch_units);
  const tasks = spec.tasks.filter((task) => task.process_id === plan.task.process_id);
  const demand = tasks.reduce((sum, task) => sum + Number(task.demand.value), 0);
  const share = tasks.length > 1 && demand > 0 ? Number(plan.task.demand.value) / demand : 1;
  const unitsPerDay = Number(report.workload?.simulated_units_per_day) * share;
  const count = share === 1 ? Number(report.workload?.jobs_per_day) : Math.ceil(unitsPerDay / batch);
  const playback = { plan, calendar, byRobot, jobs, endSeconds: 3 * DAY, presentationVersion: LIVE_PLAYBACK_VERSION,
    sourceReportDigest: report.replay?.report_content_digest, noPath: new Set(), delayedJobs: 0, unscheduledJobs: 0, completedUnits: [] };
  if (!plan.robots.length || !Number.isFinite(service) || service <= 0) return { ...playback, reason: 'Нет положительной мощности парка; задания не воспроизводятся' };
  if (!Number.isInteger(count) || count < 0 || count > policy.max_jobs_per_day || !(batch > 0)) throw new TypeError('Неподдерживаемый объём заданий');
  const ratio = Number(plan.fleet.effective_capacity.value) / Number(plan.fleet.nominal_capacity.value);
  const nominal = service * Math.min(1, Math.max(0, ratio)), exchange = plan.task.exchange;
  const load = exchange.mode === 'TOTAL' ? Number(exchange.total_time.value) / 2 : Number(exchange.load_time?.value || 0);
  const unload = exchange.mode === 'TOTAL' ? Number(exchange.total_time.value) / 2 : Number(exchange.unload_time?.value || 0);
  const travel = Math.max(0, nominal - load - unload) / 2;
  const speed = Math.max(.05, Math.min(3, Number(plan.fleet.operating_speed?.value || 1)));
  const free = plan.robots.map(() => 0);
  const resources = new Map((report.resources || []).filter((r) => r.capacity > 0).map((r) => [r.stage, Array(Number(r.capacity)).fill(0)]));
  for (let day = 0; day < 2; day += 1) for (let index = 0; index < count; index += 1) {
    const sequence = day * count + index, release = day * calendar.hours + index * calendar.hours / count;
    // Prune only before the monotonically increasing arrival; later jobs can start earlier than a delayed one.
    for (let i = active.length - 1; i >= 0; i -= 1) if (active[i].end < release) active.splice(i, 1);
    const candidates = free.map((time, robot) => ({ time, robot })).sort((a, b) => a.time - b.time || (a.robot - sequence % free.length + free.length) % free.length - (b.robot - sequence % free.length + free.length) % free.length);
    let selected;
    for (const candidate of candidates) {
      const route = safeRoute(plan, candidate.robot, sequence);
      if (routeIsSafe(plan, route, candidate.robot)) { selected = { ...candidate, route }; break; }
      playback.noPath.add(candidate.robot);
    }
    if (!selected) { playback.unscheduledJobs += 1; continue; }
    const { robot, route } = selected, units = Math.min(batch, Math.max(0, unitsPerDay - index * batch)), fraction = units / batch;
    if (units <= 0) continue;
    const definitions = plan.cleaning
      ? [['TRANSIT', Math.max(nominal * .1, length(route.outbound) / speed), route.outbound],
        ['WORK', Math.max(nominal * .8 * fraction, length(route.work) / speed), route.work],
        ['RETURN', Math.max(nominal * .1, length(route.returning) / speed), route.returning]]
      : plan.stationary ? [['WORK', service * fraction, [route.home, route.home]]]
        : [['TO_LOAD', length(route.toLoad) / speed, route.toLoad], ['LOAD', load * fraction, [route.pickup, route.pickup]],
          ['OUTBOUND', Math.max(travel, length(route.outbound) / speed), route.outbound], ['UNLOAD', unload * fraction, [route.handoff, route.handoff]],
          ['RETURN', Math.max(travel, length(route.returning) / speed), route.returning]];
    if (!plan.stationary) definitions.push(['ALLOWANCE', Math.max(0, service - nominal) * fraction, [route.home, route.home]]);
    let start = Math.max(release, free[robot]), offsets = [], cursor = 0;
    for (const [stage, duration] of definitions) { offsets.push(cursor); const slots = resources.get(stage); if (slots) start = Math.max(start, Math.min(...slots) - cursor); cursor += duration; }
    const build = () => definitions.flatMap(([stage, duration, points], i) => stageSegments(stage, start + offsets[i], duration, points));
    let segments = build();
    // Reserve swept paths, including operation dwell and turns; all waiting remains in a separate bay.
    for (let attempts = 0; attempts <= active.length; attempts += 1) {
      const conflicts = active.filter((job) => job.robot !== robot && job.end >= start && job.start <= start + cursor
        && job.segments.some((a) => segments.some((b) => sweptSeparation(a, b) < 2 * plan.footprint.radius + plan.footprint.clearance)));
      if (!conflicts.length) break;
      start = Math.max(...conflicts.map((job) => job.end)) + EPS; segments = build();
    }
    for (let i = 0; i < definitions.length; i += 1) {
      const slots = resources.get(definitions[i][0]);
      if (slots) slots[slots.indexOf(Math.min(...slots))] = start + offsets[i] + definitions[i][1];
    }
    const job = { sequence, robot, units, release, start, end: start + cursor, segments, route,
      timeline: definitions.map(([stage, duration], i) => ({ stage, start: start + offsets[i], end: start + offsets[i] + duration })) };
    if (cursor > service * fraction + EPS || start > Math.max(release, free[robot]) + EPS) playback.delayedJobs += 1;
    free[robot] = job.end; jobs.push(job); byRobot[robot].push(job); active.push(job);
  }
  playback.completedUnits = byRobot.map((rows) => { const prefix = [0]; for (const row of rows) prefix.push(prefix.at(-1) + row.units); return prefix; });
  if (playback.noPath.size) playback.reason = 'Часть маршрутов недоступна при заданном footprint и препятствиях; роботы остаются на стоянках';
  return playback;
}

export function safeFrameAt(playback, elapsedSeconds) {
  const { plan, calendar, byRobot } = playback, time = Math.max(0, elapsedSeconds), work = calendar.workAt(time), open = calendar.isOpen(time);
  let completedUnits = 0;
  const robots = plan.robots.map((robot, index) => {
    const rows = byRobot[index]; let left = 0, right = rows.length;
    while (left < right) { const mid = (left + right) >>> 1; if (rows[mid].end <= work) left = mid + 1; else right = mid; }
    completedUnits += playback.completedUnits[index]?.[left] || 0;
    const job = rows[left], active = job && job.start <= work;
    const route = active ? job.route : safeRoute(plan, index);
    const entry = active ? job.segments.find((segment) => segment.start <= work && work < segment.end) : null;
    const stage = playback.noPath.has(index) && !rows.length ? 'NO_PATH' : !open ? 'OFF_SHIFT' : entry?.stage || (job?.release <= work ? 'WAIT_RESOURCE' : 'WAITING');
    const progress = entry ? (work - entry.start) / (entry.end - entry.start) : 0;
    const pose = entry ? pointAlong([entry.a, entry.b], progress) : { ...route.home, yaw: 0 };
    const carrying = active && ['OUTBOUND', 'UNLOAD'].includes(entry?.stage);
    return { ...robot, ...pose, stage, stageLabel: STAGE_LABELS[stage], progress, completedJobs: left,
      jobSequence: active ? job.sequence : null, units: active ? job.units : 0, areaLabel: route.areaLabel, route,
      carrying, cargoState: carrying ? 'ON_ROBOT' : 'AT_HANDOFF', cleaning: open && entry?.stage === 'WORK' && plan.cleaning,
      footprint: plan.footprint, nextStartSeconds: job && !active ? calendar.offsetAt(job.start) : null,
      waitReason: stage === 'WAIT_RESOURCE' ? 'Забронирован общий проход или точка передачи; ожидание на отдельной стоянке' : stage === 'NO_PATH' ? playback.reason : null };
  });
  return { elapsedSeconds: time, workSeconds: work, robots, completedUnits,
    nextStartSeconds: Math.min(...robots.map((robot) => robot.nextStartSeconds ?? Infinity)),
    completedJobs: robots.reduce((sum, robot) => sum + robot.completedJobs, 0), open, presentationVersion: LIVE_PLAYBACK_VERSION,
    sourceReportDigest: playback.sourceReportDigest, delayedJobs: playback.delayedJobs,
    finished: time >= playback.endSeconds, reason: playback.reason };
}
