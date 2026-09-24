import { createRandom, pick, range } from '../core/random.js';
import { normalizeConfig } from './config.js';
import { generateAirportWorld } from './airport.js';
import { generateHospitalWorld } from './hospital.js';
import { addPerson } from './template-base.js';
import { robotProfile, robotTypesForTemplate } from './robot-catalog.js';
import { parseScenarioSpec } from '../integration/scenario-spec.js';
import { generateProcessZoneWorld } from './process-zone.js';

const COLORS = {
  ground: [0.18, 0.29, 0.22], asphalt: [0.18, 0.21, 0.21], concrete: [0.48, 0.52, 0.50],
  wall: [0.73, 0.78, 0.75], wallDark: [0.30, 0.38, 0.36], roof: [0.18, 0.25, 0.24],
  frame: [0.13, 0.20, 0.21], beam: [0.92, 0.48, 0.12], pallet: [0.48, 0.30, 0.14],
  safety: [0.95, 0.72, 0.10], charger: [0.12, 0.75, 0.48], glass: [0.31, 0.64, 0.69]
};
const BOX_COLORS = [[0.57, 0.37, 0.19], [0.72, 0.54, 0.30], [0.35, 0.55, 0.48], [0.26, 0.42, 0.58], [0.62, 0.29, 0.20]];

function block(position, scale, color, options = {}) {
  return { position, scale, color, yaw: options.yaw || 0, type: options.type || 'block', meta: options.meta || null, editorId: options.editorId, editorKind: options.editorKind, solid: options.solid };
}

function addRack(scene, random, x, z, occupied, row, bay) {
  const editorId = `base:rack:${row + 1}:${bay + 1}`;
  const editable = { editorId, editorKind: 'rack' };
  const rackWidth = 2.25;
  const rackDepth = 1.15;
  const rackHeight = 4.7;
  const post = 0.10;
  for (const px of [-rackWidth / 2, rackWidth / 2]) {
    for (const pz of [-rackDepth / 2, rackDepth / 2]) {
      scene.staticObjects.push(block([x + px, rackHeight / 2, z + pz], [post, rackHeight, post], COLORS.frame, { type: 'metal', ...editable }));
    }
  }
  for (const level of [0.75, 2.0, 3.25, 4.5]) {
    scene.staticObjects.push(block([x, level, z - rackDepth / 2], [rackWidth + .2, .12, .12], COLORS.beam, { type: 'safety', ...editable }));
    scene.staticObjects.push(block([x, level, z + rackDepth / 2], [rackWidth + .2, .12, .12], COLORS.beam, { type: 'safety', ...editable }));
    scene.staticObjects.push(block([x, level - .08, z], [rackWidth, .08, rackDepth], COLORS.frame, { type: 'metal', ...editable }));
    if (level < 4.5 && random() < occupied) {
      scene.staticObjects.push(block(
        [x + range(random, -.2, .2), level + .28, z + range(random, -.12, .12)],
        [range(random, 1.55, 1.95), .48, .82], pick(random, BOX_COLORS),
        { type: 'cargo', ...editable, meta: { label: `Стеллаж ${row + 1}-${bay + 1}`, loadKg: Math.round(range(random, 280, 790)) } }
      ));
      scene.staticObjects.push(block([x, level + .02, z], [1.9, .12, .92], COLORS.pallet, { type: 'metal', ...editable }));
    }
  }
}

function addTree(scene, random, x, z) {
  scene.staticObjects.push(block([x, 1.1, z], [.42, 2.2, .42], [0.30, 0.19, 0.09]));
  const green = pick(random, [[.14,.38,.19], [.18,.46,.23], [.22,.42,.18]]);
  scene.staticObjects.push(block([x, 3.0, z], [2.2, 2.5, 2.2], green));
}

function generateWarehouseWorld(rawConfig, scenario = null) {
  const config = normalizeConfig(rawConfig, { extendedFleet: Boolean(scenario) });
  const random = createRandom(config.seed);
  const scene = { config, random, staticObjects: [], solids: [], interactables: [], routes: [], people: [], labels: [], spawn: [0, 1.72, config.depth / 2 + 13] };
  const width = config.width;
  const depth = config.depth;
  const front = depth / 2;
  const back = -depth / 2;
  const wallHeight = 7.5;
  const doorWidth = 5.4;

  scene.staticObjects.push(block([0, -.35, 0], [width + 34, .6, depth + 40], COLORS.ground, { type: 'ground' }));
  scene.staticObjects.push(block([0, -.03, depth / 2 + 9], [16, .08, 18], COLORS.asphalt, { type: 'asphalt' }));
  scene.staticObjects.push(block([0, .01, 0], [width, .12, depth], [0.48, 0.51, 0.49], { type: 'floor' }));
  scene.staticObjects.push(block([0, wallHeight + .2, 0], [width + .6, .35, depth + .6], COLORS.roof, { type: 'roof' }));

  const wallThickness = .42;
  const wallDefs = [
    { p: [-width / 2, wallHeight / 2, 0], s: [wallThickness, wallHeight, depth] },
    { p: [width / 2, wallHeight / 2, 0], s: [wallThickness, wallHeight, depth] },
    { p: [0, wallHeight / 2, back], s: [width, wallHeight, wallThickness] },
    { p: [-(width + doorWidth) / 4, wallHeight / 2, front], s: [(width - doorWidth) / 2, wallHeight, wallThickness] },
    { p: [(width + doorWidth) / 4, wallHeight / 2, front], s: [(width - doorWidth) / 2, wallHeight, wallThickness] },
    // Верхняя перемычка видима, но не участвует в плоской коллизии игрока.
    { p: [0, 6.1, front], s: [doorWidth, 2.8, wallThickness], solid: false }
  ];
  wallDefs.forEach(({ p, s, solid = true }, index) => {
    const editorId = `base:wall:${index + 1}`;
    scene.staticObjects.push(block(p, s, COLORS.wall, { type: 'wall', editorId, editorKind: 'wall', solid }));
    if (solid) scene.solids.push({ position: p, scale: s, editorId });
  });

  scene.staticObjects.push(block([0, 5.55, front + .28], [8.5, 1.15, .18], COLORS.wallDark, { type: 'sign' }));
  scene.staticObjects.push(block([0, 5.55, front + .39], [5.8, .54, .10], COLORS.charger, { type: 'sign' }));
  for (const x of [-width * .32, width * .32]) {
    scene.staticObjects.push(block([x, 3.8, front + .23], [5.5, 2.2, .10], COLORS.glass, { type: 'glass' }));
  }

  const usableWidth = width - 12;
  const spacingX = usableWidth / Math.max(config.rackRows - 1, 1);
  const rackXs = Array.from({ length: config.rackRows }, (_, i) => -usableWidth / 2 + spacingX * i);
  const rackStart = back + 4.2;
  const rackEnd = front - 8.3;
  const baySpacing = 2.7;
  const bayCount = Math.max(4, Math.floor((rackEnd - rackStart) / baySpacing));
  rackXs.forEach((x, row) => {
    for (let bay = 0; bay < bayCount; bay += 1) addRack(scene, random, x, rackStart + bay * baySpacing, config.occupancy / 100, row, bay);
    const colliderZ = (rackStart + rackStart + (bayCount - 1) * baySpacing) / 2;
    const colliderDepth = (bayCount - 1) * baySpacing + 1.4;
    for (let bay = 0; bay < bayCount; bay += 1) scene.solids.push({ position: [x, 2.4, rackStart + bay * baySpacing], scale: [2.55, 4.9, 1.4], editorId: `base:rack:${row + 1}:${bay + 1}` });
    scene.labels.push({ text: `РЯД ${String.fromCharCode(65 + row)}`, position: [x, 5.35, rackEnd + .8], kind: 'warehouse' });
  });

  const aisleXs = [];
  for (let i = 0; i < rackXs.length - 1; i += 1) aisleXs.push((rackXs[i] + rackXs[i + 1]) / 2);
  aisleXs.unshift(-width / 2 + 3.2);
  aisleXs.push(width / 2 - 3.2);

  const crossAisleZ = front - 5.0;
  for (let x = -width / 2 + 5; x <= width / 2 - 5; x += 8) {
    for (let z = back + 4; z <= front - 4; z += 9) scene.staticObjects.push(block([x, 7.0, z], [3.4, .07, .34], [.86, 1.0, .92], { type: 'light' }));
  }
  const chargerCount = Math.max(5, config.robotCount);
  // Радиус AMR и защитная оболочка требуют запаса на одновременный вход/выход
  // из соседних мест; 1.55 м приводили к взаимной блокировке на поворотах.
  const chargerSpacing = 2;
  for (let i = 0; i < chargerCount; i += 1) {
    const x = -width / 2 + 2.0 + i * chargerSpacing;
    scene.staticObjects.push(block([x, .28, crossAisleZ + 1.6], [1.0, .45, 1.25], COLORS.charger, { type: 'charger', meta: { label: `Зарядная позиция ${i + 1}` } }));
  }
  const chargerAreaWidth = (chargerCount - 1) * chargerSpacing + 1.4;
  scene.staticObjects.push(block([-width / 2 + 2 + (chargerCount - 1) * chargerSpacing / 2, .03, crossAisleZ + 1.6], [chargerAreaWidth, .03, 2.1], [0.12, .36, .25]));

  const stationX = width / 2 - 3.4;
  scene.staticObjects.push(block([stationX, .5, crossAisleZ + 1.7], [4.8, 1.0, 2.1], COLORS.safety, { type: 'station', meta: { label: 'Зона приёмки и отгрузки' } }));
  scene.solids.push({ position: [stationX, .5, crossAisleZ + 1.7], scale: [4.8, 1.0, 2.1] });
  scene.labels.push({ text: 'ПРИЁМКА / ОТГРУЗКА', position: [stationX, 2.25, crossAisleZ + 1.7], kind: 'warehouse' });
  scene.labels.push({ text: 'ЗАРЯДНАЯ ЗОНА', position: [-width / 2 + 4.8, 1.65, crossAisleZ + 1.7], kind: 'warehouse' });

  const rackAisles = aisleXs.slice(0, rackXs.length);
  const pickupCandidates = [0, 1, 2].flatMap(slot => rackAisles.map((aisleX, aisleIndex) => {
      const bay = Math.min(bayCount - 1, Math.round(slot * (bayCount - 1) / 2));
      const row = Math.min(rackXs.length - 1, aisleIndex);
      return { position: [aisleX, rackStart + bay * baySpacing], rackRow: row, bay, label: `Ряд ${String.fromCharCode(65 + row)}, ячейка ${bay + 1}` };
    }));
  for (let i = 0; i < config.robotCount; i += 1) {
    const profile = robotProfile(
      scenario?.internalProfile || robotTypesForTemplate('warehouse')[i % 3]
    );
    if (scenario) {
      profile.modelCode = scenario.equipmentModelId;
      profile.label = scenario.equipmentModelId;
      profile.maxLoadKg = scenario.payloadKg;
    }
    const initialAisle = config.robotCount <= rackAisles.length
      ? Math.round(i * (rackAisles.length - 1) / Math.max(1, config.robotCount - 1))
      : i % rackAisles.length;
    const initialSlot = Math.floor(i / rackAisles.length) % 3;
    const initialPickupIndex = initialSlot * rackAisles.length + initialAisle;
    const pickup = pickupCandidates[initialPickupIndex];
    const aisleX = pickup.position[0];
    const deepZ = pickup.position[1];
    const chargerX = -width / 2 + 2 + i * chargerSpacing;
    const outboundZ = crossAisleZ - .20 - (i % 2) * 1.50;
    const returnZ = crossAisleZ - 3.50 - (i % 2) * 1.50;
    scene.routes.push({
      id: i + 1,
      ...profile,
      pickupCandidates,
      initialPickupIndex,
      pickupCandidateStride: config.robotCount,
      pickupAisleWaypoints: [2, 4, 7],
      pickupWaypoint: 3,
      dropWaypoint: 5,
      chargeWaypoint: 0,
      dropPosition: [stationX - 1.7, crossAisleZ + 1.7],
      points: [
        [chargerX, crossAisleZ + 1.6],
        [chargerX, outboundZ],
        [aisleX, outboundZ],
        [aisleX, deepZ],
        [aisleX, outboundZ],
        [stationX - 3.1, outboundZ],
        [stationX - 3.1, returnZ],
        [aisleX, returnZ],
        [chargerX, returnZ],
        [chargerX, crossAisleZ + 1.6]
      ],
      equipmentModelId: scenario?.equipmentModelId || null,
      zoneId: scenario?.zoneId || null,
      unitsPerTrip: scenario?.unitsPerTrip || 1,
      taskProfileKind: scenario?.taskKind || null,
      exchangeTimeS: scenario?.exchangeTimeS ?? null,
      speed: scenario?.maxSpeedMS ?? (range(random, 1.0, 1.35) * profile.speedFactor),
      phase: ((i + .15) / config.robotCount) % 1
    });
  }

  // Люди не ходят параллельно с AMR между стеллажами: один контролёр
  // наблюдает за потоком из безопасной зоны за приёмной станцией.
  const controller = [stationX, crossAisleZ + 3.35];
  addPerson(scene, controller[0], controller[1], [[.92,.55,.10], [.22,.45,.68]], {
    role: 'Контролёр роботизированной зоны',
    activity: 'Наблюдение за приёмкой, отгрузкой и состоянием AMR',
    waypoints: [controller, [controller[0] + .12, controller[1]], [controller[0], controller[1] + .10]],
    stopPoints: [controller],
    stationary: true,
    pose: 'standing'
  });

  for (let i = 0; i < 18; i += 1) {
    let x = range(random, -width / 2 - 14, width / 2 + 14);
    let z = range(random, back - 15, front + 19);
    if (Math.abs(x) < 10 && z > front - 2) x += x < 0 ? -12 : 12;
    if (Math.abs(x) < width / 2 + 3 && z > back - 3 && z < front + 3) continue;
    addTree(scene, random, x, z);
  }
  for (let x = -7; x <= 7; x += 2) scene.staticObjects.push(block([x, .04, front + 7], [.12, .03, 5], [.88, .86, .59]));

  scene.layout = { rackXs, aisleXs, bayCount, front, back, crossAisleZ };
  if (scenario) {
    scene.scenarioSpec = scenario.spec;
    scene.scenario = Object.freeze({
      revisionId: scenario.revisionId,
      zoneId: scenario.zoneId,
      equipmentModelId: scenario.equipmentModelId,
      demandPerDay: scenario.demandPerDay,
      unitsPerTrip: scenario.unitsPerTrip,
      taskIntervalS: scenario.taskIntervalS,
      exchangeTimeS: scenario.exchangeTimeS
    });
  }
  return scene;
}

export function generateWorld(rawConfig) {
  const config = normalizeConfig(rawConfig);
  if (config.template === 'airport') return generateAirportWorld(config);
  if (config.template === 'hospital') return generateHospitalWorld(config);
  return generateWarehouseWorld(config);
}

export function generateWorldFromScenarioSpec(source) {
  const generated = generateWorldsFromScenarioSpec(source);
  const first = generated.zones.find(zone => zone.supported);
  if (!first) throw new TypeError(`ScenarioSpec не содержит зон с поддерживаемой 3D-сценой: ${generated.zones.map(zone => `${zone.zone.name}: ${zone.reason}`).join('; ')}`);
  return first.scene;
}

function applyScenarioToScene(scene, parsed, zoneEntry) {
  const scenario = zoneEntry.scenario;
  if (scenario.processType !== 'palletizing') {
    scene.routes.forEach((route, index) => {
      const profile = robotProfile(scenario.internalProfile);
      Object.assign(route, profile, {
        id: index + 1, modelCode: scenario.equipmentModelId, label: scenario.equipmentModelId,
        maxLoadKg: scenario.payloadKg, equipmentModelId: scenario.equipmentModelId,
        zoneId: scenario.zoneId, taskId: scenario.taskId, scenarioRouteId: scenario.routeId,
        pickupId: scenario.pickupId, dropoffId: scenario.dropoffId,
        unitsPerTrip: scenario.unitsPerTrip,
        taskProfileKind: scenario.taskKind, exchangeTimeS: scenario.exchangeTimeS,
        speed: scenario.maxSpeedMS, kind: scenario.processType === 'delivery' ? 'medical' : route.kind
      });
    });
  }
  scene.scenarioSpec = parsed.spec;
  scene.scenario = Object.freeze({ ...scenario });
  scene.labels.push({ text: `АКТИВНАЯ ЗОНА · ${scenario.zoneName.toUpperCase()}`, position: [0, 6.6, 0], kind: scene.config.template });
  if (zoneEntry.zone.polygon) {
    const polygon = zoneEntry.zone.polygon;
    const xs = polygon.map(point => point[0]); const zs = polygon.map(point => point[1]);
    const centerX = (Math.min(...xs) + Math.max(...xs)) / 2; const centerZ = (Math.min(...zs) + Math.max(...zs)) / 2;
    const scale = Math.min((scene.config.width - 8) / Math.max(1, Math.max(...xs) - Math.min(...xs)), (scene.config.depth - 8) / Math.max(1, Math.max(...zs) - Math.min(...zs)));
    const normalized = polygon.map(point => [(point[0] - centerX) * scale, (point[1] - centerZ) * scale]);
    normalized.forEach((point, index) => {
      const next = normalized[(index + 1) % normalized.length]; const dx = next[0] - point[0]; const dz = next[1] - point[1];
      scene.staticObjects.push(block([(point[0] + next[0]) / 2, .045, (point[1] + next[1]) / 2], [Math.hypot(dx, dz), .035, .12], [.16,.88,.65], { type: 'zone-outline', yaw: Math.atan2(dx, dz) - Math.PI / 2, solid: false }));
    });
    scene.geometryReference = Object.freeze({ zoneId: scenario.zoneId, polygon: polygon.map(point => [...point]), mode: 'REFERENCE_OVERLAY' });
  }
  scene.conceptualZone = scenario.geometryMode === 'REPRESENTATIVE';
  return scene;
}

function generateZoneScene(parsed, zoneEntry) {
  const source = parsed.spec; const scenario = zoneEntry.scenario; const facility = source.facility || {};
  const seed = parsed.zones.length === 1 ? source.seed : `${source.seed}:${scenario.zoneId}`;
  const config = normalizeConfig({
    template: source.template,
    seed,
    width: facility.width_m || DEFAULT_SCENARIO_WIDTH,
    depth: facility.depth_m || DEFAULT_SCENARIO_DEPTH,
    rackRows: 5,
    robotCount: scenario.quantity,
    occupancy: facility.occupancy_percent || 72
  }, { extendedFleet: true });
  let scene;
  if (scenario.processType === 'cleaning' || scenario.processType === 'palletizing') scene = generateProcessZoneWorld(config, scenario);
  else if (source.template === 'airport') scene = generateAirportWorld(config);
  else if (source.template === 'hospital') scene = generateHospitalWorld(config);
  else scene = generateWarehouseWorld(config, { ...scenario, spec: parsed.spec });
  return applyScenarioToScene(scene, parsed, zoneEntry);
}

export function generateWorldsFromScenarioSpec(source) {
  const parsed = parseScenarioSpec(source);
  return Object.freeze({
    spec: parsed.spec,
    revisionId: parsed.revisionId,
    zones: Object.freeze(parsed.zones.map(entry => Object.freeze({
      zone: entry.zone, supported: entry.supported, reason: entry.reason || null,
      scene: entry.supported ? generateZoneScene(parsed, entry) : null
    })))
  });
}

const DEFAULT_SCENARIO_WIDTH = 48;
const DEFAULT_SCENARIO_DEPTH = 38;
