import { createSafePlan, safeRoute, VISUAL_FOOTPRINT } from '../integration/safe-playback-v2.js';
import { createBaseScene, makeBlock, addSolid, addPerson } from './template-base.js';

export const safeWorldPoint = (plan, pose) => [pose.x - plan.width / 2, pose.y - plan.height / 2];

export function generateSafeFacilityWorld(config, spec, zoneId) {
  const plan = createSafePlan(spec, zoneId);
  if (!plan) throw new TypeError('Для процесса нет связанного безопасного условного плана');
  const scene = createBaseScene({ ...config, width: plan.width, depth: plan.height });
  scene.facilityPlan = plan;
  scene.safePlaybackPlan = plan;
  scene.staticObjects = scene.staticObjects.filter((object) => !['roof', 'light'].includes(object.type));
  for (const object of scene.staticObjects.filter(object => object.type === 'wall')) {
    if (object.solid === false) continue;
    object.position[1] = 1.6; object.scale[1] = 3.2;
    if (plan.cleaning && object.editorId === 'base:wall:3') {
      object.type = 'glass'; object.color = [.32, .64, .71];
    }
  }
  scene.staticObjects = scene.staticObjects.filter(object => !(object.type === 'wall' && object.solid === false));
  for (const solid of scene.solids.filter(object => object.editorId?.startsWith('base:wall:'))) {
    solid.position[1] = 1.6; solid.scale[1] = 3.2;
  }
  for (const area of plan.areas) {
    const [x, z] = safeWorldPoint(plan, { x: area.x + area.width / 2, y: area.y + area.height / 2 });
    scene.staticObjects.push(makeBlock([x, .06, z], [area.width - .1, .04, area.height - .1], [.23, .38, .41], { type: 'floor' }));
    scene.labels.push({ text: area.label.toUpperCase(), position: [x, 1.3, area.y + 1 - plan.height / 2], kind: spec.template });
  }
  for (const rect of plan.walls) {
    const [x, z] = safeWorldPoint(plan, { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 });
    addSolid(scene, [x, 1.55, z], [rect.width, 3.1, rect.height], [.64, .76, .76], { type: 'wall' });
  }
  for (const rect of plan.environment) {
    const [x, z] = safeWorldPoint(plan, { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 });
    if (rect.type === 'person') {
      addPerson(scene, x, z, [plan.clinic ? [.42, .70, .72] : plan.cleaning ? [.34, .55, .72] : [.82, .58, .28]],
        { role: rect.role, activity: 'В выделенной зоне', stationary: true, waypoints: [[x, z], [x, z]] });
    } else if (rect.overhead) {
      scene.staticObjects.push(makeBlock([x, rect.elevation, z], [rect.width, .28, rect.height], rect.color, { type: rect.type }));
    } else {
      const object = makeBlock([x, rect.onRack ? 1.65 : rect.elevation / 2, z], [rect.width, rect.elevation, rect.height], rect.color,
        { type: rect.type, meta: { detailed: true, onRack: Boolean(rect.onRack) } });
      scene.staticObjects.push(object);
      scene.solids.push({ position: object.position, scale: object.scale, yaw: 0 });
      if (rect.patient) addPerson(scene, x, z, [[.70, .86, .83]],
        { role: 'Пациент', activity: 'Отдых', stationary: true, pose: 'lying', allowInsideSolid: true,
          waypoints: [[x, z], [x, z]] });
    }
  }
  for (const person of plan.people) {
    const [x, z] = safeWorldPoint(plan, person);
    addPerson(scene, x, z, [[.4, .7, .75]], { role: person.label, activity: 'В выделенной зоне ожидания',
      stationary: true, waypoints: [[x, z], [x, z]] });
  }
  if (plan.cleaning) {
    const back = -plan.height / 2 - 12;
    const body = [.82, .88, .91], wing = [.64, .77, .83];
    scene.staticObjects.push(makeBlock([0, 1.25, back], [2.3, 1.5, 17], body, { type: 'decor' }));
    scene.staticObjects.push(makeBlock([0, 1.48, back + 9], [1.6, .9, 2.5], body, { type: 'decor' }));
    for (const side of [-1, 1]) {
      scene.staticObjects.push(makeBlock([side * 5, 1.5, back + 1], [8, .22, 3.5], wing, { type: 'decor' }));
      scene.staticObjects.push(makeBlock([side * 2.7, 1.65, back - 6], [4, .18, 1.5], wing, { type: 'decor' }));
      scene.staticObjects.push(makeBlock([side * 1.15, .45, back + 2], [.24, .9, .24], [.30, .37, .40], { type: 'decor' }));
    }
    scene.staticObjects.push(makeBlock([0, 2.35, back - 7], [.3, 2.1, 2.3], wing, { type: 'decor' }));
  }
  if (!plan.clinic && !plan.cleaning) {
    for (let y = 2; y < plan.height - 2; y += 4.4) {
      const [x, z] = safeWorldPoint(plan, { x: 9, y });
      scene.staticObjects.push(makeBlock([x, .065, z], [.08, .018, 1.6], [.83, .70, .30], { type: 'floor' }));
    }
  }
  scene.routes = plan.robots.map((robot) => {
    const route = safeRoute(plan, robot.ordinal);
    const points = [...route.toLoad, ...route.outbound, ...route.returning].filter((p, i, all) => !i || p.x !== all[i - 1].x || p.y !== all[i - 1].y)
      .map((p) => safeWorldPoint(plan, p));
    if (points.length < 2) points.push([...points[0]]);
    return { id: robot.ordinal + 1, points, kind: plan.clinic ? 'medical' : plan.cleaning ? 'cleaning' : 'warehouse',
      pickupWaypoint: 0, dropWaypoint: Math.max(1, route.outbound.length - 1), chargeWaypoint: 0,
      dropPosition: safeWorldPoint(plan, route.handoff), speed: 1, phase: 0, radius: VISUAL_FOOTPRINT.radius,
      visualFootprint: VISUAL_FOOTPRINT };
  });
  scene.spawn = [0, 1.72, plan.height / 2 - 2];
  return scene;
}
