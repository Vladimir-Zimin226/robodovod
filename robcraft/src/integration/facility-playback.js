// Presentation v1: one plan and one clock for 2D and 3D. Coordinates describe
// an illustrative facility, never a surveyed plan or the analytical distance.
export const FACILITY_TIME_SCALE = 60;
export const FACILITY_STAGE_LABELS = Object.freeze({
  LOAD: 'Приём питания', OUTBOUND: 'Доставка в отделение', UNLOAD: 'Передача питания',
  RETURN: 'Возврат на раздачу', WORK: 'Уборка участка',
  ALLOWANCE: 'Технологическая пауза', WAITING: 'Ожидание задания', OFF_SHIFT: 'Вне рабочего окна',
  WAIT_RESOURCE: 'Ожидание точки обслуживания',
});
const DAY = 86400;

export function supportsFacilityPlan(spec) {
  return spec?.schema_version === 'scenario-spec-v2' && (
    (spec.template === 'airport' && spec.profile?.calculation_profile === 'CLEANING_AREA_V1' && spec.profile.process_code === 'airport_terminal_cleaning')
    || (spec.template === 'hospital' && spec.profile?.calculation_profile === 'DELIVERY_CYCLE_V1' && spec.profile.process_code === 'clinic_food')
  );
}

export function createFacilityPlan(spec, zoneId = spec.zones[0]?.zone_id) {
  if (!supportsFacilityPlan(spec)) return null;
  const zone = spec.zones.find(item => item.zone_id === zoneId);
  const task = spec.tasks.find(item => item.zone_id === zoneId && item.process_id === spec.profile.process_id)
    || spec.tasks.find(item => item.zone_id === zoneId);
  const fleet = spec.fleet.find(item => item.zone_id === zoneId && item.process_id === task?.process_id);
  if (!zone || !task || !fleet) return null;
  const clinic = spec.template === 'hospital';
  const areas = clinic ? [
    { id: 'food', label: 'Пищеблок / раздача', x: 16, y: 27, width: 16, height: 5 },
    { id: 'corridor', label: 'Главный коридор', x: 21, y: 0, width: 6, height: 27 },
    ...[0, 1, 2].flatMap(row => [0, 1].map(side => ({
      id: `ward-${row * 2 + side + 1}`, label: `Отделение ${row * 2 + side + 1}`,
      x: side ? 27 : 0, y: row * 9, width: 21, height: 8,
    }))),
  ] : [
    { id: 'checkin', label: 'Зал регистрации', x: 0, y: 0, width: 15, height: 26 },
    { id: 'waiting', label: 'Зал ожидания', x: 16, y: 0, width: 15, height: 26 },
    { id: 'gates', label: 'Выходы на посадку', x: 32, y: 0, width: 16, height: 26 },
    { id: 'service', label: 'Служебный проход', x: 0, y: 27, width: 48, height: 5 },
  ];
  const furniture = clinic ? areas.filter(area => area.id.startsWith('ward')).flatMap(area => [
    { type: 'bed', x: area.x + 2, y: area.y + 1, width: 3, height: 1.8 },
    { type: 'bed', x: area.x + 13, y: area.y + 1, width: 3, height: 1.8 },
    { type: 'desk', x: area.x + 3, y: area.y + 6, width: 2, height: 1 },
  ]) : areas.slice(0, 3).flatMap((area, i) => [0, 1, 2].map(column => ({
    type: i === 0 ? 'counter' : i === 1 ? 'seat' : 'gate',
    x: area.x + 2 + column * 4, y: 2.5, width: 2.5, height: 1.3,
  })));
  // Clinic partitions have a four-metre doorway centred on each handoff.
  const walls = clinic ? areas.filter(area => area.id.startsWith('ward')).flatMap(area => {
    const x = area.x === 0 ? 21 : 27;
    return [
      { x: area.x, y: area.y + 8.5, width: 21, height: .2 },
      { x, y: area.y, width: .2, height: 2 },
      { x, y: area.y + 6, width: .2, height: 2 },
    ];
  }) : [];
  const robots = Array.from({ length: fleet.selected_fleet }, (_, ordinal) => ({
    id: `${fleet.fleet_id}.${ordinal + 1}`, ordinal, fleetId: fleet.fleet_id,
    modelId: fleet.model_id, zoneId, taskId: task.task_id, routeId: task.route_ref,
  }));
  return { kind: 'FACILITY_PROCESS', template: spec.template, zoneId, label: zone.label,
    width: 48, height: 32, areas, furniture, walls, robots, task, fleet,
    geometrySource: zone.geometry_source, geometryRef: zone.geometry_ref,
    assumptionRef: zone.assumption_ref, route: spec.routes.find(item => item.route_id === task.route_ref) || null };
}

export function facilityRoute(plan, ordinal, sequence = ordinal) {
  if (plan.template === 'hospital') {
    const area = plan.areas[2 + sequence % 6];
    const handoff = { x: area.x === 0 ? 18 : 30, y: area.y + 4 };
    const outbound = [{ x: 24, y: 29 }, { x: 24, y: handoff.y }, handoff];
    return { areaId: area.id, areaLabel: area.label, outbound, work: outbound,
      returning: [...outbound].reverse(), home: outbound[0], handoff };
  }
  const area = plan.areas[(ordinal + Math.floor(sequence / Math.max(1, plan.robots.length))) % 3];
  const lane = Math.floor(ordinal / 3) % 3;
  const x = area.x + 2 + lane * 3.5;
  const work = [];
  for (let stripe = 0; stripe < 3; stripe += 1) {
    work.push({ x: x + stripe, y: stripe % 2 ? 24 : 6 }, { x: x + stripe, y: stripe % 2 ? 6 : 24 });
  }
  const home = { x: plan.areas[ordinal % 3].x + 2.5 + lane * 3.5, y: 29 };
  // Each microtask covers a strip of open floor, rather than a perimeter loop.
  return { areaId: area.id, areaLabel: area.label,
    outbound: [home, { x: work[0].x, y: 29 }, work[0]], work,
    returning: [work.at(-1), { x: work.at(-1).x, y: 29 }, home], home, handoff: work.at(-1) };
}

export function pointAlong(points, fraction) {
  const lengths = points.slice(1).map((point, i) => Math.hypot(point.x - points[i].x, point.y - points[i].y));
  let remaining = Math.max(0, Math.min(1, fraction)) * lengths.reduce((a, b) => a + b, 0);
  for (let i = 0; i < lengths.length; i += 1) {
    if (remaining <= lengths[i] || i === lengths.length - 1) {
      const amount = lengths[i] ? Math.min(1, remaining / lengths[i]) : 0;
      return { x: points[i].x + (points[i + 1].x - points[i].x) * amount,
        y: points[i].y + (points[i + 1].y - points[i].y) * amount,
        yaw: Math.atan2(points[i + 1].x - points[i].x, points[i + 1].y - points[i].y) };
    }
    remaining -= lengths[i];
  }
  return { ...points[0], yaw: 0 };
}

function calendarFor(spec, report) {
  const origin = report.model_start?.seconds_from_midnight ?? Math.min(...spec.operating_windows.map(w => Number(w.start_time.value)));
  const windows = spec.operating_windows.map(w => {
    let start = Number(w.start_time.value);
    if (start < origin) start += DAY;
    return [start - origin, start - origin + Number(w.duration.value) * 3600];
  }).sort((a, b) => a[0] - b[0]);
  const hours = windows.reduce((sum, [a, b]) => sum + b - a, 0);
  const offsetAt = offset => {
    const day = Math.floor(offset / hours);
    let rest = offset - day * hours;
    for (const [start, end] of windows) {
      if (rest < end - start) return day * DAY + start + rest;
      rest -= end - start;
    }
    return (day + 1) * DAY + windows[0][0];
  };
  const workAt = time => {
    const day = Math.floor(time / DAY), rest = time - day * DAY;
    return day * hours + windows.reduce((sum, [start, end]) => sum + Math.max(0, Math.min(rest, end) - start), 0);
  };
  const isOpen = time => windows.some(([start, end]) => time % DAY >= start && time % DAY < end);
  return { hours, offsetAt, workAt, isOpen };
}

// Reconstruct illustrative jobs from saved uniform arrivals, stages, fleet and
// effective service. This is not an event log exported by C23. Saved KPIs stay
// authoritative. Browser floating point is only used for visual positioning.
export function createFacilityPlayback(plan, spec, report) {
  const calendar = calendarFor(spec, report);
  const service = Number(report.trace.find(node => node.output_ref === 'service.effective-seconds')?.value);
  if (!Number.isFinite(service) || service <= 0 || !plan.robots.length) return { plan, calendar, jobs: [], byRobot: plan.robots.map(() => []), reason: 'Нет положительной мощности парка' };
  const jobsPerDay = Number(report.workload.jobs_per_day);
  if (!Number.isInteger(jobsPerDay) || jobsPerDay < 0 || jobsPerDay > 10000) throw new TypeError('Неподдерживаемый объём заданий');
  const batch = Number(report.workload.batch_units);
  const unitsPerDay = Number(report.workload.simulated_units_per_day);
  const ratio = Number(plan.fleet.effective_capacity.value) / Number(plan.fleet.nominal_capacity.value);
  const nominal = service * ratio;
  const exchange = plan.task.exchange;
  const load = exchange.mode === 'TOTAL' ? Number(exchange.total_time.value) / 2 : Number(exchange.load_time?.value || 0);
  const unload = exchange.mode === 'TOTAL' ? Number(exchange.total_time.value) / 2 : Number(exchange.unload_time?.value || 0);
  const travel = Math.max(0, nominal - load - unload) / 2;
  const stages = plan.template === 'hospital'
    ? [['LOAD', load], ['OUTBOUND', travel], ['UNLOAD', unload], ['RETURN', travel], ['ALLOWANCE', Math.max(0, service - nominal)]]
    : [['WORK', nominal], ['ALLOWANCE', Math.max(0, service - nominal)]];
  const free = plan.robots.map(() => 0), byRobot = plan.robots.map(() => []), jobs = [];
  const resourceSlots = new Map((report.resources || []).map(resource => [resource.stage, Array(Number(resource.capacity)).fill(0)]));
  // Warmup + measurement arrivals, and one completion grace day, as in C23.
  for (let day = 0; day < 2; day += 1) for (let index = 0; index < jobsPerDay; index += 1) {
    const release = day * calendar.hours + index * calendar.hours / jobsPerDay;
    const robot = free.indexOf(Math.min(...free));
    let current = Math.max(release, free[robot]);
    const units = Math.min(batch, Math.max(0, unitsPerDay - index * batch));
    const timeline = stages.map(([stage, duration]) => {
      const slots = resourceSlots.get(stage);
      const slot = slots ? slots.indexOf(Math.min(...slots)) : null;
      if (slots) current = Math.max(current, slots[slot]);
      const start = current;
      current += duration * units / batch;
      if (slots) slots[slot] = current;
      return { stage, start, end: current };
    });
    const job = { sequence: day * jobsPerDay + index, robot, units, release,
      start: timeline[0].start, end: current, timeline };
    free[robot] = current; jobs.push(job); byRobot[robot].push(job);
  }
  return { plan, calendar, jobs, byRobot, endSeconds: 3 * DAY };
}

export function facilityFrameAt(playback, elapsedSeconds) {
  const { plan, calendar, byRobot } = playback;
  const time = Math.max(0, elapsedSeconds), work = calendar.workAt(time);
  const open = calendar.isOpen(time);
  const robots = plan.robots.map((robot, index) => {
    const jobs = byRobot[index];
    // Binary search makes seeking/restart independent of elapsed duration.
    let left = 0, right = jobs.length;
    while (left < right) { const mid = (left + right) >>> 1; if (jobs[mid].end <= work) left = mid + 1; else right = mid; }
    const job = jobs[left];
    const active = job && job.start <= work;
    const route = facilityRoute(plan, index, active ? job.sequence : (jobs[left - 1]?.sequence ?? index));
    const stageEntry = active ? job.timeline.find(entry => work >= entry.start && work < entry.end) : null;
    const previousStage = active ? job.timeline.filter(entry => entry.end <= work).at(-1) : null;
    const motionStage = stageEntry?.stage || previousStage?.stage;
    const stage = !open ? 'OFF_SHIFT' : stageEntry?.stage || (active ? 'WAIT_RESOURCE' : 'WAITING');
    const progress = stageEntry ? (work - stageEntry.start) / (stageEntry.end - stageEntry.start) : 0;
    const motionProgress = stageEntry ? progress : previousStage ? 1 : 0;
    let points = [route.home, route.home], amount = 0;
    if (active) {
      if (plan.template === 'airport') {
        // Small travel parts frame the productive coverage sweep.
        if (motionStage === 'WORK') {
          if (motionProgress < .1) { points = route.outbound; amount = motionProgress / .1; }
          else if (motionProgress < .9) { points = route.work; amount = (motionProgress - .1) / .8; }
          else { points = route.returning; amount = (motionProgress - .9) / .1; }
        }
      } else if (motionStage === 'OUTBOUND') { points = route.outbound; amount = motionProgress; }
      else if (motionStage === 'UNLOAD') { points = route.outbound; amount = 1; }
      else if (motionStage === 'RETURN') { points = route.returning; amount = motionProgress; }
    }
    const pose = pointAlong(points, amount);
    return { ...robot, ...pose, stage, stageLabel: FACILITY_STAGE_LABELS[stage], progress,
      completedJobs: left, jobSequence: active ? job.sequence : null,
      units: active ? job.units : 0, areaLabel: route.areaLabel, route,
      carrying: active && ['OUTBOUND', 'UNLOAD'].includes(motionStage),
      cleaning: open && stage === 'WORK' && progress >= .1 && progress < .9,
      nextStartSeconds: job && !active ? calendar.offsetAt(job.start) : null };
  });
  return { elapsedSeconds: time, robots, completedJobs: robots.reduce((sum, r) => sum + r.completedJobs, 0),
    nextStartSeconds: Math.min(...robots.map(r => r.nextStartSeconds ?? Infinity)), open,
    finished: time >= (playback.endSeconds || 3 * DAY), reason: playback.reason };
}
