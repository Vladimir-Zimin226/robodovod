import { robotProfile } from './robot-catalog.js';
import { addExteriorDetails, addSolid, createBaseScene, makeBlock } from './template-base.js';

function contractRoute(id, scenario, points, extra = {}) {
  const profile = robotProfile(scenario.internalProfile);
  profile.modelCode = scenario.equipmentModelId;
  profile.label = scenario.equipmentModelId;
  profile.maxLoadKg = scenario.payloadKg;
  return {
    id, ...profile, ...extra, points, equipmentModelId: scenario.equipmentModelId,
    zoneId: scenario.zoneId, unitsPerTrip: scenario.unitsPerTrip,
    taskProfileKind: scenario.taskKind, exchangeTimeS: scenario.exchangeTimeS,
    speed: scenario.maxSpeedMS, phase: 0, pickupWaypoint: 1,
    dropWaypoint: Math.max(2, points.length - 2), chargeWaypoint: 0
  };
}

function cleaningWorld(config, scenario) {
  const scene = createBaseScene(config, { concrete: [.52,.58,.57], wall: [.76,.82,.80], roof: [.15,.25,.24] });
  addExteriorDetails(scene, [.13,.72,.61]);
  const halfW = config.width / 2 - 4; const halfD = config.depth / 2 - 4;
  scene.labels.push({ text: `КОНЦЕПТУАЛЬНАЯ ЗОНА · ${scenario.zoneName.toUpperCase()}`, position: [0, 3.1, scene.layout.front - 2], kind: config.template });
  scene.labels.push({ text: 'МАРШРУТ ПОКРЫТИЯ', position: [0, 1.8, 0], kind: config.template });
  const coverage = [];
  for (let row = 0, z = -halfD; z <= halfD; row += 1, z += 3) coverage.push([row % 2 ? -halfW : halfW, z], [row % 2 ? halfW : -halfW, z]);
  for (let i = 0; i < scenario.quantity; i += 1) {
    const x = -halfW + i * Math.min(1.5, (halfW * 2) / Math.max(1, scenario.quantity - 1));
    const charger = [x, scene.layout.front - 2.1];
    scene.staticObjects.push(makeBlock([charger[0], .06, charger[1]], [.9,.05,1.1], [.12,.70,.58], { type: 'charger' }));
    scene.routes.push(contractRoute(i + 1, scenario, [charger, ...coverage, charger], { kind: 'cleaning', dropPosition: coverage.at(-1) }));
  }
  scene.layout = { ...scene.layout, objectName: 'Зона уборки', zone: scenario.zoneName, processType: 'cleaning' };
  return scene;
}

function palletizingWorld(config, scenario) {
  const scene = createBaseScene(config, { concrete: [.48,.51,.49], wall: [.73,.78,.75], roof: [.18,.25,.24] });
  addExteriorDetails(scene, [.94,.57,.10]);
  scene.labels.push({ text: `КОНЦЕПТУАЛЬНАЯ ЗОНА · ${scenario.zoneName.toUpperCase()}`, position: [0, 3.1, scene.layout.front - 2], kind: 'warehouse' });
  scene.labels.push({ text: 'ПАЛЛЕТИЗАЦИЯ · КОНВЕЙЕРНЫЙ ЦИКЛ', position: [0, 3.0, 0], kind: 'warehouse' });
  const conveyorZ = -config.depth / 2 + 4;
  addSolid(scene, [0, .55, conveyorZ], [Math.min(config.width - 8, 80), 1, 1.4], [.16,.20,.20], { type: 'station', meta: { label: 'Подающий конвейер' } });
  const columns = Math.max(1, Math.floor((config.width - 6) / 3));
  for (let i = 0; i < scenario.quantity; i += 1) {
    const column = i % columns; const row = Math.floor(i / columns);
    const x = -(columns - 1) * 1.5 + column * 3; const z = conveyorZ + 2.2 + row * 3;
    scene.staticObjects.push(makeBlock([x, .08, z + .6], [1.2,.12,1.2], [.50,.31,.15], { type: 'cargo' }));
    scene.routes.push(contractRoute(i + 1, scenario, [[x, z], [x, z + .01], [x, z + .02]], {
      kind: 'palletizing', stationaryCycle: true, cycleDurationS: Math.max(1, scenario.exchangeTimeS || 5),
      dropPosition: [x, z + .6]
    }));
  }
  scene.layout = { ...scene.layout, objectName: 'Ячейки паллетизации', zone: scenario.zoneName, processType: 'palletizing' };
  return scene;
}

export function generateProcessZoneWorld(config, scenario) {
  return scenario.processType === 'cleaning' ? cleaningWorld(config, scenario) : palletizingWorld(config, scenario);
}
