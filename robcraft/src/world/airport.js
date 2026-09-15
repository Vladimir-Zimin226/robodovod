import { addExteriorDetails, addPerson, addSolid, createBaseScene, makeBlock, pick, range } from './template-base.js';
import { robotProfile, robotTypesForTemplate } from './robot-catalog.js';

export function generateAirportWorld(config) {
  const scene = createBaseScene(config, {
    concrete: [.63, .66, .65], wall: [.78, .82, .83], roof: [.16, .23, .27], asphalt: [.20, .22, .24]
  });
  const { width, depth, rackRows: gateCount, robotCount, occupancy } = config;
  const { front, back } = scene.layout;
  const accent = [.18, .62, .82];
  addExteriorDetails(scene, accent);
  scene.labels.push({ text: 'РЕГИСТРАЦИЯ', position: [0, 3.0, front - 5.2], kind: 'airport' });
  scene.labels.push({ text: 'КОНТРОЛЬ БЕЗОПАСНОСТИ', position: [0, 3.35, 1.5], kind: 'airport' });

  // Стойки регистрации по сторонам от центрального входного потока.
  for (const side of [-1, 1]) {
    for (let i = 0; i < 4; i += 1) {
      const x = side * (6.5 + i * 3.0);
      addSolid(scene, [x, .62, front - 5.2], [2.15, 1.15, 1.0], [.18, .36, .48], { type: 'checkin' });
      scene.staticObjects.push(makeBlock([x, 1.55, front - 5.65], [1.1, .72, .08], [.25, .78, .92]));
    }
  }

  // Линии досмотра образуют прозрачный проход в центре терминала.
  for (let i = -2; i <= 2; i += 1) {
    const x = i * 3.0;
    addSolid(scene, [x - .9, .48, 1.5], [.45, .92, 3.8], [.16, .23, .26]);
    addSolid(scene, [x + .9, .48, 1.5], [.45, .92, 3.8], [.16, .23, .26]);
    scene.staticObjects.push(makeBlock([x, 2.25, .4], [2.2, .18, .24], accent));
  }

  // Залы ожидания и выходы на посадку.
  const gateSpacing = (width - 10) / Math.max(gateCount - 1, 1);
  for (let gate = 0; gate < gateCount; gate += 1) {
    const x = -width / 2 + 5 + gate * gateSpacing;
    scene.staticObjects.push(makeBlock([x, 3.3, back + .28], [3.7, 2.1, .10], scene.colors.glass, { type: 'glass' }));
    scene.staticObjects.push(makeBlock([x, 4.8, back + .4], [2.5, .45, .12], accent));
    scene.labels.push({ text: `ВЫХОД ${gate + 1}`, position: [x, 5.35, back + .75], kind: 'airport' });
    for (let row = 0; row < 3; row += 1) {
      const z = back + 4 + row * 1.6;
      for (const dx of [-1.15, 0, 1.15]) addSolid(scene, [x + dx, .42, z], [.86, .7, .72], [.18, .31, .38], { type: 'seat' });
    }
  }

  // Багажная лента в глубине, по которой проходит роботизированная логистика.
  addSolid(scene, [-width / 2 + 3.2, .55, -4.8], [3.8, 1.0, 11], [.10, .16, .18], { type: 'baggage' });
  scene.labels.push({ text: 'БАГАЖНАЯ ЛИНИЯ', position: [-width / 2 + 3.2, 2.0, -4.8], kind: 'airport' });
  for (let z = -9; z <= 0; z += 2.1) scene.staticObjects.push(makeBlock([-width / 2 + 3.2, 1.1, z], [2.2, .55, 1.35], pick(scene.random, [[.54,.16,.12],[.12,.28,.48],[.55,.42,.10]])));

  // Пассажирская активность локализована у стоек. Люди не пересекают
  // служебные полосы AMR в глубине терминала.
  const queueCount = Math.min(3, Math.max(1, Math.round(occupancy / 30)));
  const queueDesks = [6.5, -6.5, 9.5];
  for (let i = 0; i < queueCount; i += 1) {
    const point = [queueDesks[i], front - 3.65];
    addPerson(scene, point[0], point[1], [[.74,.24,.22],[.19,.38,.62],[.64,.52,.22]], {
      role: 'Пассажир', activity: `Ожидает регистрации у стойки ${i + 1}`,
      waypoints: [point, [point[0] + .10, point[1]], [point[0], point[1] + .08]],
      stopPoints: [point], stationary: true
    });
  }
  for (const [index, x] of [6.5, -6.5].entries()) {
    const point = [x, front - 4.35];
    addPerson(scene, point[0], point[1], [[.18,.44,.58],[.22,.50,.60]], {
      role: 'Агент регистрации', activity: `Работа за стойкой регистрации ${index + 1}`,
      waypoints: [point, [point[0] + .08, point[1]], [point[0], point[1] + .06]],
      stopPoints: [point], stationary: true
    });
  }
  const guardPoint = [0, front - 2.7];
  addPerson(scene, guardPoint[0], guardPoint[1], [[.12,.20,.28]], {
    role: 'Сотрудник безопасности', activity: 'Контроль входной зоны терминала',
    waypoints: [guardPoint, [.10, guardPoint[1]], [0, guardPoint[1] + .08]],
    stopPoints: [guardPoint], stationary: true
  });
  const consolePosition = [width / 2 - 3.2, .56, front - 3.25];
  addSolid(scene, consolePosition, [2.3, 1.0, 1.0], [.12, .28, .30], { type: 'station', meta: { label: 'Пульт диспетчера AMR' } });
  const operatorPoint = [consolePosition[0], front - 2.35];
  addPerson(scene, operatorPoint[0], operatorPoint[1], [[.16,.42,.38]], {
    role: 'Диспетчер AMR', activity: 'Контроль парка и служебных маршрутов',
    waypoints: [operatorPoint, [operatorPoint[0] + .08, operatorPoint[1]], [operatorPoint[0], operatorPoint[1] + .06]],
    stopPoints: [operatorPoint], stationary: true, pose: 'seated'
  });

  const serviceOutboundZ = front - 7.4;
  const serviceReturnZ = front - 9.0;
  for (let i = 0; i < robotCount; i += 1) {
    const profile = robotProfile(robotTypesForTemplate('airport')[i % 2]);
    const chargerX = -width / 2 + 2.15 + (i % 4) * 1.45;
    const chargerZ = front - 2.2 - Math.floor(i / 4) * 1.55;
    scene.staticObjects.push(makeBlock([chargerX, .06, chargerZ], [1.0, .05, 1.05], [.10, .55, .72], { type: 'charger' }));
    scene.staticObjects.push(makeBlock([chargerX, .5, chargerZ + .48], [.72, .86, .12], [.20, .78, .92], { type: 'light' }));
    const laneX = -width / 2 + 6.2 + (i % Math.max(2, gateCount)) * ((width - 12.4) / Math.max(1, gateCount - 1));
    scene.routes.push({
      id: i + 1, kind: 'baggage', ...profile,
      pickupWaypoint: 1, dropWaypoint: 4, chargeWaypoint: 0, dropPosition: [0, back + 9.5],
      points: [[chargerX, chargerZ], [chargerX, serviceOutboundZ], [laneX, serviceOutboundZ], [laneX, back + 9.5], [0, back + 9.5], [width / 2 - 3.2, back + 9.5], [width / 2 - 3.2, serviceReturnZ], [chargerX, serviceReturnZ], [chargerX, chargerZ]],
      speed: range(scene.random, .9, 1.25) * profile.speedFactor, phase: scene.random()
    });
  }
  scene.labels.push({ text: 'ЗАРЯДКА AMR', position: [-width / 2 + 2.8, 1.75, front - 2.2], kind: 'airport' });
  scene.layout = { ...scene.layout, objectName: 'Аэропорт', zone: 'Пассажирский терминал' };
  return scene;
}
