import { createFacilityPlan, facilityRoute } from '../integration/facility-playback.js';
import { createBaseScene, makeBlock, addSolid, addPerson } from './template-base.js';

export const facilityWorldPoint = point => [point.x - 24, point.y - 16];

export function generateFacilityWorld(config, spec, zoneId) {
  const plan = createFacilityPlan(spec, zoneId);
  if (!plan) throw new TypeError('Нет связанного задания и парка для плана объекта');
  const scene = createBaseScene({ ...config, width: plan.width, depth: plan.height });
  scene.facilityPlan = plan;
  // An open cutaway lets the viewer see operations inside the whole facility.
  scene.staticObjects = scene.staticObjects.filter(object => !['roof', 'light'].includes(object.type));
  for (const object of [...scene.staticObjects, ...scene.solids]) if (object.type === 'wall' || object.editorId?.startsWith('base:wall:')) {
    object.position = [object.position[0], .55, object.position[2]];
    object.scale = [object.scale[0], 1.1, object.scale[2]];
  }
  for (const area of plan.areas) {
    const x = area.x + area.width / 2 - 24, z = area.y + area.height / 2 - 16;
    scene.staticObjects.push(makeBlock([x, .085, z], [area.width - .15, .04, area.height - .15],
      area.id === 'corridor' || area.id === 'service' ? [.26,.40,.44] : [.48,.59,.62], { type: 'floor' }));
    scene.labels.push({ text: area.label.toUpperCase(), position: [x, 1.65, area.y - 14.8], kind: spec.template });
  }
  for (const wall of plan.walls) addSolid(scene, [wall.x + wall.width / 2 - 24, .55, wall.y + wall.height / 2 - 16],
    [wall.width, 1.1, wall.height], [.68,.81,.82], { type: 'wall' });
  for (const item of plan.furniture) {
    const x = item.x + item.width / 2 - 24, z = item.y + item.height / 2 - 16;
    addSolid(scene, [x, .4, z], [item.width, .8, item.height], item.type === 'bed' ? [.73,.84,.88] : [.22,.48,.52], { type: item.type });
    if (item.type === 'bed') {
      scene.staticObjects.push(makeBlock([x - 1, .9, z], [.6,.16,1.3], [.91,.97,.98]));
      addPerson(scene, x, z, [[.6,.8,.85]], { role: 'Пациент', activity: 'В отделении', stationary: true,
        pose: 'lying', allowInsideSolid: true, waypoints: [[x,z],[x+.01,z]] });
    }
  }
  if (spec.template === 'hospital') {
    addSolid(scene, [-5, .65, 14], [3, 1.3, 1.2], [.23,.65,.55], { type: 'supply' });
    addPerson(scene, -7, 14, [[.75,.9,.86]], { role: 'Сотрудник пищеблока', activity: 'Подготовка питания', stationary: true, waypoints: [[-7,14],[-7,14.01]] });
  } else {
    for (const x of [-18,-2,14]) addPerson(scene, x, -12, [[.3,.5,.7]], { role: 'Пассажир', activity: 'У стойки', stationary: true, waypoints: [[x,-12],[x,-11.99]] });
  }
  scene.routes = plan.robots.map(robot => {
    const route = facilityRoute(plan, robot.ordinal);
    const raw = [...route.outbound, ...route.work, ...route.returning];
    const points = raw.filter((p, i) => !i || p.x !== raw[i-1].x || p.y !== raw[i-1].y).map(facilityWorldPoint);
    return { id: robot.ordinal + 1, points, kind: spec.template === 'hospital' ? 'medical' : 'cleaning',
      pickupWaypoint: 0, dropWaypoint: Math.max(1, route.outbound.length - 1), chargeWaypoint: 0,
      dropPosition: facilityWorldPoint(route.handoff), speed: 1, phase: 0 };
  });
  scene.spawn = [0, 1.72, 13];
  return scene;
}
