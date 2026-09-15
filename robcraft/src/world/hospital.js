import { addExteriorDetails, addPerson, addSolid, createBaseScene, makeBlock, range } from './template-base.js';
import { robotProfile, robotTypesForTemplate } from './robot-catalog.js';

function addBed(scene, x, z, occupied) {
  addSolid(scene, [x, .55, z], [1.05, .55, 2.05], [.82, .88, .87], { type: 'bed' });
  scene.staticObjects.push(makeBlock([x, .91, z - .68], [.92, .22, .55], occupied ? [.48, .72, .68] : [.68, .82, .80]));
  scene.staticObjects.push(makeBlock([x, .35, z + 1.0], [1.08, .72, .10], [.28, .44, .43]));
  return { x, z, occupied };
}

function addPartitionWithDoor(scene, x, z, width, alongX) {
  const gap = 1.5;
  const part = (width - gap) / 2;
  if (alongX) {
    addSolid(scene, [x - (width + gap) / 4, 1.55, z], [part, 3.1, .22], [.72, .82, .79]);
    addSolid(scene, [x + (width + gap) / 4, 1.55, z], [part, 3.1, .22], [.72, .82, .79]);
  } else {
    addSolid(scene, [x, 1.55, z - (width + gap) / 4], [.22, 3.1, part], [.72, .82, .79]);
    addSolid(scene, [x, 1.55, z + (width + gap) / 4], [.22, 3.1, part], [.72, .82, .79]);
  }
}

export function generateHospitalWorld(config) {
  const scene = createBaseScene(config, {
    concrete: [.68, .73, .71], wall: [.83, .88, .85], roof: [.18, .29, .28], asphalt: [.34, .40, .38]
  });
  const { width, depth, rackRows: roomsPerWing, robotCount, occupancy } = config;
  const { front, back } = scene.layout;
  const accent = [.16, .70, .57];
  addExteriorDetails(scene, accent);
  scene.labels.push({ text: 'ПРИЁМНОЕ ОТДЕЛЕНИЕ', position: [-5.2, 2.4, front - 5.0], kind: 'hospital' });

  // Центральная приёмная оставляет свободный путь от входа к главному коридору.
  addSolid(scene, [-5.2, .65, front - 5.0], [6.5, 1.2, 1.25], [.18, .50, .45], { type: 'reception' });
  scene.staticObjects.push(makeBlock([-5.2, 1.55, front - 5.45], [3.6, .62, .09], accent));
  for (let i = 0; i < 5; i += 1) addSolid(scene, [3.2 + i * 1.15, .42, front - 5.0], [.82, .72, .72], [.22, .38, .36], { type: 'seat' });

  const corridorHalf = 2.0;
  const wingWidth = width / 2 - corridorHalf - 1.0;

  const usableDepth = depth - 13;
  const roomDepth = usableDepth / roomsPerWing;
  const beds = [];
  for (let room = 1; room < roomsPerWing; room += 1) {
    const z = back + 2 + room * roomDepth;
    addPartitionWithDoor(scene, -corridorHalf - wingWidth / 2, z, wingWidth, true);
    addPartitionWithDoor(scene, corridorHalf + wingWidth / 2, z, wingWidth, true);
  }
  for (let room = 0; room < roomsPerWing; room += 1) {
    const z = back + 2 + room * roomDepth + roomDepth / 2;
    addPartitionWithDoor(scene, -corridorHalf, z, roomDepth, false);
    addPartitionWithDoor(scene, corridorHalf, z, roomDepth, false);
    const occupied = scene.random() < occupancy / 100;
    beds.push(addBed(scene, -corridorHalf - wingWidth * .53, z, occupied));
    beds.push(addBed(scene, corridorHalf + wingWidth * .53, z, scene.random() < occupancy / 100));
    scene.labels.push({ text: `ПАЛАТА ${room + 1}A`, position: [-corridorHalf - .35, 2.55, z], kind: 'hospital' });
    scene.labels.push({ text: `ПАЛАТА ${room + 1}B`, position: [corridorHalf + .35, 2.55, z], kind: 'hospital' });
    scene.staticObjects.push(makeBlock([-corridorHalf - .42, 2.25, z], [.10, .55, 1.3], [.20, .64, .56]));
    scene.staticObjects.push(makeBlock([corridorHalf + .42, 2.25, z], [.10, .55, 1.3], [.20, .64, .56]));
  }

  // Аптека/склад расходников в конце коридора.
  addSolid(scene, [0, .75, back + 2.0], [3.1, 1.4, 1.3], [.22, .48, .43], { type: 'supply' });
  scene.labels.push({ text: 'СКЛАД РАСХОДНИКОВ', position: [0, 2.15, back + 2.0], kind: 'hospital' });
  // В коридоре остаётся только роботный поток. Пациенты лежат на кроватях,
  // а врачи находятся непосредственно в палатах.
  const occupiedBeds = beds.filter(bed => bed.occupied);
  const patientBeds = (occupiedBeds.length ? occupiedBeds : beds.slice(0, 1)).slice(0, 4);
  patientBeds.forEach((bed, index) => {
    const point = [bed.x, bed.z];
    addPerson(scene, bed.x, bed.z, [[.52,.64,.76],[.63,.55,.72]], {
      role: 'Пациент', activity: `Отдыхает в палате ${Math.floor(index / 2) + 1}`,
      waypoints: [point, [bed.x, bed.z + .08], [bed.x + .05, bed.z + .08]],
      stopPoints: [point], stationary: true, pose: 'lying', allowInsideSolid: true, phase: 0
    });
  });
  beds.slice(0, 2).forEach((bed, index) => {
    const side = Math.sign(bed.x) || 1;
    const point = [bed.x - side * 1.35, bed.z];
    addPerson(scene, point[0], point[1], [[.76,.86,.84],[.30,.62,.70]], {
      role: index ? 'Медсестра' : 'Врач', activity: `Наблюдение за пациентом в палате ${index + 1}`,
      waypoints: [point, [point[0], point[1] + .10], [point[0] + side * .06, point[1] + .10]],
      stopPoints: [point], stationary: true, pose: 'standing', phase: 0
    });
  });

  for (let i = 0; i < robotCount; i += 1) {
    const profile = robotProfile(robotTypesForTemplate('hospital')[i % 2]);
    const side = i % 2 ? -1 : 1;
    const targetZ = back + 3.5 + (i % roomsPerWing) * roomDepth;
    const chargerX = -1.35 + (i % 4) * .9;
    const chargerZ = back + 4.0 + Math.floor(i / 4) * 1.25;
    scene.staticObjects.push(makeBlock([chargerX, .06, chargerZ], [.72, .05, 1.0], [.12, .67, .53], { type: 'charger' }));
    scene.staticObjects.push(makeBlock([chargerX, .43, chargerZ - .46], [.5, .72, .10], [.22, .83, .68], { type: 'light' }));
    scene.routes.push({
      id: i + 1, kind: 'medical', ...profile,
      pickupWaypoint: 1, dropWaypoint: 3, chargeWaypoint: 0, dropPosition: [side * 1.65, targetZ],
      points: [[chargerX, chargerZ], [0, back + 3.2], [0, targetZ], [side * 1.25, targetZ], [side * 1.25, front - 7], [0, front - 7], [chargerX, chargerZ]],
      speed: range(scene.random, .65, .95) * profile.speedFactor, phase: scene.random()
    });
  }
  scene.labels.push({ text: 'ЗАРЯДКА МЕДИЦИНСКИХ AMR', position: [0, 1.7, back + 4.0], kind: 'hospital' });
  scene.layout = { ...scene.layout, objectName: 'Больница', zone: 'Лечебный корпус' };
  return scene;
}
