const REQUEST_FIELDS = new Set([
  'schema_version', 'request_id', 'tenant_id', 'project_id', 'scenario_spec',
  'mode', 'peak_factor', 'sla', 'resources', 'limits',
]);
const SPEC_FIELDS = new Set([
  'schema_version', 'revision_id', 'source', 'template', 'seed', 'analysis',
  'versions', 'profile', 'operating_windows', 'zones', 'routes', 'fleet',
  'tasks', 'finance', 'assumptions', 'trace_node_refs', 'warnings',
]);
const REPORT_FIELDS = new Set([
  'schema_version', 'report_id', 'request_id', 'tenant_id', 'project_id',
  'scenario_revision_id', 'status', 'engineering_claim', 'time_basis',
  'workload', 'capacity', 'queue', 'utilization', 'sla', 'resources',
  'limitations', 'trace', 'versions', 'replay',
]);
const SPEEDS = new Set([0.5, 1, 2, 4]);
const CAPACITY_VERDICTS = new Set(['CONSISTENT', 'DEVIATION', 'OVERLOADED', 'N_A', 'INPUT_MISMATCH']);
const SLA_VERDICTS = new Set(['PASS', 'FAIL', 'CONDITIONAL', 'NOT_EVALUATED']);

function object(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${path} должен быть объектом`);
  }
  return value;
}

function exact(value, fields, path) {
  object(value, path);
  const unknown = Object.keys(value).filter((key) => !fields.has(key));
  if (unknown.length) throw new TypeError(`${path}: неизвестные поля: ${unknown.join(', ')}`);
}

export function parseSimulationBundle(request, report) {
  exact(request, REQUEST_FIELDS, 'SimulationRequest');
  exact(request.scenario_spec, SPEC_FIELDS, 'ScenarioSpec');
  exact(report, REPORT_FIELDS, 'SimulationReport');
  if (request.schema_version !== 'simulation-request-v1') throw new TypeError('Неподдерживаемая версия SimulationRequest');
  if (request.scenario_spec.schema_version !== 'scenario-spec-v2') throw new TypeError('2D требует ScenarioSpec v2');
  if (report.schema_version !== 'simulation-report-v1') throw new TypeError('Неподдерживаемая версия SimulationReport');
  if (report.engineering_claim !== 'PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION') {
    throw new TypeError('SimulationReport содержит недопустимое инженерное утверждение');
  }
  if (!CAPACITY_VERDICTS.has(report.capacity?.verdict) || !SLA_VERDICTS.has(report.sla?.verdict)) {
    throw new TypeError('SimulationReport содержит неизвестный capacity/SLA verdict');
  }
  if (report.sla.verdict === 'PASS' && (
    request.sla === null || report.sla.sla_minutes === null
    || report.sla.target_fraction === null || report.sla.on_time_fraction === null
  )) {
    throw new TypeError('SimulationReport не может показывать SLA PASS без оценённых входов');
  }
  const spec = request.scenario_spec;
  if (request.request_id !== report.request_id
      || request.tenant_id !== report.tenant_id
      || request.project_id !== report.project_id
      || spec.revision_id !== report.scenario_revision_id) {
    throw new TypeError('SimulationReport не связан с текущим запросом/ревизией');
  }
  if (typeof spec.seed !== 'string' || !spec.seed || !/^sha256:[0-9a-f]{64}$/.test(report.replay?.report_content_digest || '')) {
    throw new TypeError('Отсутствует seed или digest воспроизведения');
  }
  return { request, spec, report };
}

export function hasCapacityWarning(report) {
  return ['DEVIATION', 'OVERLOADED', 'INPUT_MISMATCH'].includes(report.capacity.verdict);
}

function hash(value) {
  let result = 2166136261;
  for (const symbol of String(value)) {
    result ^= symbol.charCodeAt(0);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function routePoints(zone, key) {
  const inset = 30 + hash(key) % 25;
  return [
    { x: zone.x + inset, y: zone.y + zone.height - inset },
    { x: zone.x + zone.width * 0.45, y: zone.y + inset },
    { x: zone.x + zone.width - inset, y: zone.y + zone.height * 0.55 },
    { x: zone.x + inset, y: zone.y + zone.height - inset },
  ];
}

export function buildSimulationScene(spec) {
  object(spec, 'ScenarioSpec');
  const zones = spec.zones.map((zone, index) => {
    const columns = Math.min(2, spec.zones.length);
    const row = Math.floor(index / columns);
    const column = index % columns;
    return {
      id: zone.zone_id,
      label: zone.label,
      geometrySource: zone.geometry_source,
      geometryLabel: zone.geometry_source === 'PROVIDED' ? 'PROVIDED_REFERENCE' : zone.geometry_source,
      geometryRef: zone.geometry_ref,
      assumptionRef: zone.assumption_ref,
      x: 30 + column * 470,
      y: 30 + row * 250,
      width: columns === 1 ? 940 : 440,
      height: 220,
    };
  });
  const byZone = new Map(zones.map((zone) => [zone.id, zone]));
  const tasks = new Map(spec.tasks.map((task) => [task.route_ref, task]));
  const routes = spec.routes.map((route) => {
    const task = tasks.get(route.route_id);
    const zone = byZone.get(task?.zone_id) || zones[0];
    return {
      id: route.route_id,
      zoneId: zone.id,
      geometrySource: route.geometry_source,
      geometryLabel: route.geometry_source === 'PROVIDED' ? 'PROVIDED_REFERENCE' : route.geometry_source,
      geometryRef: route.geometry_ref,
      assumptionRef: route.assumption_ref,
      analyticalDistance: route.one_way_distance ? { ...route.one_way_distance } : null,
      visualOnly: true,
      points: routePoints(zone, `${spec.seed}:${route.route_id}`),
    };
  });
  for (const task of spec.tasks) {
    if (task.route_ref !== null) continue;
    const zone = byZone.get(task.zone_id);
    routes.push({
      id: `visual.${task.task_id}`,
      zoneId: task.zone_id,
      geometrySource: zone.geometrySource,
      geometryLabel: zone.geometryLabel,
      geometryRef: zone.geometryRef,
      assumptionRef: zone.assumptionRef,
      analyticalDistance: null,
      visualOnly: true,
      points: routePoints(zone, `${spec.seed}:${task.task_id}:area`),
    });
  }
  const routeByZone = new Map(routes.map((route) => [route.zoneId, route]));
  const robots = spec.fleet.flatMap((fleet) => Array.from({ length: fleet.selected_fleet }, (_, index) => ({
    id: `${fleet.fleet_id}.${index + 1}`,
    fleetId: fleet.fleet_id,
    zoneId: fleet.zone_id,
    modelId: fleet.model_id,
    routeId: routeByZone.get(fleet.zone_id)?.id || null,
    ordinal: index,
  })));
  const operations = spec.tasks.map((task) => ({
    id: task.task_id,
    zoneId: task.zone_id,
    routeId: task.route_ref,
    stages: task.exchange.mode === 'NOT_APPLICABLE'
      ? ['WORK']
      : ['LOAD', 'OUTBOUND', 'UNLOAD', 'RETURN'],
  }));
  const charging = zones.map((zone) => ({
    id: `aggregate-allowance.${zone.id}`,
    zoneId: zone.id,
    x: zone.x + zone.width - 32,
    y: zone.y + 28,
    status: 'AGGREGATE_ALLOWANCE_BADGE',
    label: 'Зарядка — в агрегированном простое; точка и цикл не моделируются',
  }));
  return { width: 1000, height: Math.max(300, 60 + Math.ceil(zones.length / 2) * 250), zones, routes, robots, operations, charging };
}

export function createTimelineState(bindingKey) {
  return { bindingKey, status: 'STOPPED', speed: 1, simulationTimeUs: 0, restart: 0 };
}

export function reduceTimeline(state, action) {
  switch (action.type) {
    case 'LOAD':
      return createTimelineState(action.bindingKey);
    case 'START':
      return { ...state, status: 'RUNNING' };
    case 'PAUSE':
      return state.status === 'RUNNING' ? { ...state, status: 'PAUSED' } : state;
    case 'STOP':
      return { ...state, status: 'STOPPED', simulationTimeUs: 0 };
    case 'RESTART':
      return { ...state, status: 'RUNNING', simulationTimeUs: 0, restart: state.restart + 1 };
    case 'SET_SPEED':
      if (!SPEEDS.has(action.speed)) throw new TypeError('Неподдерживаемая скорость');
      return { ...state, speed: action.speed };
    case 'TICK': {
      if (state.status !== 'RUNNING') return state;
      const deltaMs = Number(action.deltaMs);
      if (!Number.isFinite(deltaMs) || deltaMs < 0) throw new TypeError('Некорректный шаг timeline');
      return { ...state, simulationTimeUs: state.simulationTimeUs + Math.round(deltaMs * 1000 * state.speed) };
    }
    default:
      throw new TypeError(`Неизвестное действие timeline: ${action.type}`);
  }
}

function interpolate(points, progress) {
  const segments = points.length - 1;
  const position = (progress % 1) * segments;
  const index = Math.min(segments - 1, Math.floor(position));
  const local = position - index;
  return {
    x: points[index].x + (points[index + 1].x - points[index].x) * local,
    y: points[index].y + (points[index + 1].y - points[index].y) * local,
  };
}

export function frameAt(scene, bundle, simulationTimeUs) {
  const { spec, report } = bundle;
  const routeById = new Map(scene.routes.map((route) => [route.id, route]));
  const operationsByZone = new Map(scene.operations.map((operation) => [operation.zoneId, operation]));
  const cycleUs = 20_000_000;
  const robots = scene.robots.map((robot) => {
    const route = routeById.get(robot.routeId);
    const offset = (hash(`${spec.seed}:${robot.id}`) % cycleUs) / cycleUs;
    const progress = (simulationTimeUs / cycleUs + offset) % 1;
    const position = interpolate(route.points, progress);
    const operation = operationsByZone.get(robot.zoneId);
    const stage = operation.stages[Math.min(operation.stages.length - 1, Math.floor(progress * operation.stages.length))];
    return { ...robot, ...position, stage };
  });
  return {
    simulationTimeUs,
    scenarioRevisionId: spec.revision_id,
    reportId: report.report_id,
    reportRevisionId: report.scenario_revision_id,
    reportDigest: report.replay.report_content_digest,
    seed: spec.seed,
    robots,
    events: robots.map((robot) => ({
      type: 'VISUAL_OPERATION',
      robotId: robot.id,
      operation: robot.stage,
      simulationTimeUs,
      scenarioRevisionId: spec.revision_id,
      reportDigest: report.replay.report_content_digest,
      seed: spec.seed,
    })),
  };
}

export function deterministicCapture(request, report, simulationTimeUs = 5_000_000) {
  const bundle = parseSimulationBundle(request, report);
  const scene = buildSimulationScene(bundle.spec);
  const frame = frameAt(scene, bundle, simulationTimeUs);
  return {
    binding: {
      scenario_revision_id: frame.scenarioRevisionId,
      report_id: frame.reportId,
      report_digest: frame.reportDigest,
      seed: frame.seed,
      simulation_time_us: frame.simulationTimeUs,
    },
    geometry: scene.zones.map(({ id, geometryLabel, geometryRef, assumptionRef }) => ({ id, geometryLabel, geometryRef, assumptionRef })),
    routes: scene.routes.map(({ id, geometryLabel, analyticalDistance, visualOnly }) => ({ id, geometryLabel, analyticalDistance, visualOnly })),
    robots: frame.robots.map(({ id, stage, x, y }) => ({ id, stage, x: Number(x.toFixed(3)), y: Number(y.toFixed(3)) })),
    sla: report.sla.verdict,
    capacity: report.capacity.verdict,
  };
}
