import { sceneBindingsV2 } from '../../robcraft/src/integration/scene-bindings.js';

const CYCLE_US = 20_000_000;
const STAGES = [
  { until: 0.22, code: 'TO_PICKUP', label: 'Едет к подготовленной паллете', cargo: 'AT_PICKUP' },
  { until: 0.32, code: 'LOADING', label: 'Принимает готовую паллету', cargo: 'AT_PICKUP' },
  { until: 0.66, code: 'TO_DROPOFF', label: 'Везёт груз', cargo: 'ON_ROBOT' },
  { until: 0.76, code: 'UNLOADING', label: 'Выгрузка', cargo: 'AT_DROPOFF' },
  { until: 0.95, code: 'RETURN', label: 'Возврат', cargo: 'DELIVERED' },
  { until: 1, code: 'WAITING', label: 'Ожидание', cargo: 'DELIVERED' },
];

function hash(value) {
  let result = 2166136261;
  for (const symbol of String(value)) {
    result ^= symbol.charCodeAt(0);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function mix(a, b, t) { return a + (b - a) * t; }

function at(robot, phase) {
  const { waiting, pickup, dropoff } = robot.points;
  if (phase < 0.22) return { x: mix(waiting.x, pickup.x, phase / 0.22), y: waiting.y };
  if (phase < 0.32) return pickup;
  if (phase < 0.66) return { x: mix(pickup.x, dropoff.x, (phase - 0.32) / 0.34), y: pickup.y };
  if (phase < 0.76) return dropoff;
  if (phase < 0.95) return { x: mix(dropoff.x, waiting.x, (phase - 0.76) / 0.19), y: dropoff.y };
  return waiting;
}

export function buildWarehouseScene(spec) {
  const bindings = sceneBindingsV2(spec);
  const columns = Math.min(2, bindings.length);
  const heights = bindings.map((binding) => Math.max(300,
    211 + binding.fleet.reduce((sum, item) => sum + item.selectedFleet, 0) * 27));
  const rowY = [];
  for (let row = 0, y = 30; row < Math.ceil(bindings.length / columns); row += 1) {
    rowY.push(y);
    y += Math.max(...heights.slice(row * columns, row * columns + columns)) + 26;
  }
  const zones = bindings.map((binding, index) => {
    const column = index % columns;
    const x = 30 + column * 470;
    const y = rowY[Math.floor(index / columns)];
    const width = columns === 1 ? 940 : 440;
    const height = heights[index];
    return {
      id: binding.zoneId, label: binding.label,
      geometrySource: binding.source.geometry_source,
      geometryRef: binding.source.geometry_ref,
      assumptionRef: binding.source.assumption_ref,
      geometryLabel: 'Расположение условное',
      x, y, width, height,
      racks: [0, 1, 2].map((slot) => ({
        id: `${binding.zoneId}.rack.${slot + 1}`,
        x: x + 125 + slot * (width - 180) / 3,
        y: y + 64, width: (width - 205) / 3, height: 48,
      })),
      waiting: { id: `${binding.zoneId}.waiting`, label: 'Ожидание / зарядка', x: x + 55, y: y + height - 27 },
      receiving: { id: `${binding.zoneId}.receiving`, label: 'Передача паллеты', x: x + width * 0.38, y: y + height - 27 },
      shipping: { id: `${binding.zoneId}.shipping`, label: 'Отгрузка', x: x + width * 0.76, y: y + height - 27 },
    };
  });
  const byZone = new Map(zones.map((zone) => [zone.id, zone]));
  const routesById = new Map(spec.routes.map((route) => [route.route_id, route]));
  const tasks = bindings.flatMap((binding) => binding.tasks.map((task) => ({
    id: task.taskId, zoneId: binding.zoneId, routeId: task.routeId,
    pickupId: task.pickupId, dropoffId: task.dropoffId,
    hasRoute: task.routeId !== null,
  })));
  const tasksByZone = new Map(bindings.map((binding) => [binding.zoneId,
    tasks.filter((task) => task.zoneId === binding.zoneId && task.hasRoute)]));
  const robots = bindings.flatMap((binding) => {
    const zone = byZone.get(binding.zoneId);
    const zoneTasks = tasksByZone.get(binding.zoneId);
    let lane = 0;
    return binding.fleet.flatMap((fleet) => Array.from({ length: fleet.selectedFleet }, (_, ordinal) => {
      const index = lane++;
      const task = zoneTasks.length ? zoneTasks[index % zoneTasks.length] : null;
      const y = zone.y + 145 + index * 27;
      return {
        id: `${fleet.fleetId}.${ordinal + 1}`, fleetId: fleet.fleetId,
        zoneId: zone.id, taskId: task?.id || null, routeId: task?.routeId || null,
        ordinal, lane: index,
        points: {
          waiting: { x: zone.waiting.x, y },
          pickup: { x: zone.receiving.x, y },
          dropoff: { x: zone.shipping.x, y },
        },
      };
    }));
  });
  const routes = tasks.filter((task) => task.hasRoute).map((task) => ({
    id: task.routeId, taskId: task.id, zoneId: task.zoneId,
    geometrySource: routesById.get(task.routeId).geometry_source,
    geometryLabel: 'Расположение условное',
    geometryRef: routesById.get(task.routeId).geometry_ref,
    analyticalDistance: routesById.get(task.routeId).one_way_distance,
    visualOnly: true,
  }));
  return {
    kind: 'WAREHOUSE_TRANSPORT', width: 1000,
    height: rowY.at(-1) + Math.max(...heights.slice((rowY.length - 1) * columns)) + 30,
    zones, routes, tasks, robots,
    missingTasks: zones.filter((zone) => !tasksByZone.get(zone.id).length).map((zone) => zone.id),
  };
}

export function warehouseFrameAt(scene, bundle, simulationTimeUs) {
  const { spec, report } = bundle;
  const robots = scene.robots.map((robot) => {
    if (!robot.taskId) return { ...robot, ...robot.points.waiting, stage: 'WAITING', stageLabel: 'Ожидание задания', cargoState: null };
    const offset = (hash(`${spec.seed}:${robot.id}:${robot.taskId}`) % CYCLE_US) / CYCLE_US;
    const phase = (simulationTimeUs / CYCLE_US + offset) % 1;
    const stage = STAGES.find((item) => phase < item.until);
    return { ...robot, ...at(robot, phase), stage: stage.code, stageLabel: stage.label, cargoState: stage.cargo };
  });
  return {
    simulationTimeUs, scenarioRevisionId: spec.revision_id,
    reportId: report.report_id, reportRevisionId: report.scenario_revision_id,
    reportDigest: report.replay.report_content_digest, seed: spec.seed, robots,
    events: robots.filter((robot) => robot.taskId).map((robot) => ({
      type: 'VISUAL_OPERATION', zoneId: robot.zoneId, taskId: robot.taskId,
      routeId: robot.routeId, robotId: robot.id, operation: robot.stage,
      cargoState: robot.cargoState, simulationTimeUs,
      scenarioRevisionId: spec.revision_id,
      reportDigest: report.replay.report_content_digest, seed: spec.seed,
    })),
  };
}
