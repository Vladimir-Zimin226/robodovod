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
  for (const object of [...scene.staticObjects, ...scene.solids]) if (object.type === 'wall') {
    object.position[1] = .4; object.scale[1] = .8;
  }
  for (const area of plan.areas) {
    const [x, z] = safeWorldPoint(plan, { x: area.x + area.width / 2, y: area.y + area.height / 2 });
    scene.staticObjects.push(makeBlock([x, .06, z], [area.width - .1, .04, area.height - .1], [.23, .38, .41], { type: 'floor' }));
    scene.labels.push({ text: area.label.toUpperCase(), position: [x, 1.3, area.y + 1 - plan.height / 2], kind: spec.template });
  }
  for (const rect of [...plan.walls, ...plan.furniture]) {
    const [x, z] = safeWorldPoint(plan, { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 });
    addSolid(scene, [x, .4, z], [rect.width, .8, rect.height], [.48, .65, .67], { type: rect.type || 'wall' });
  }
  for (const person of plan.people) {
    const [x, z] = safeWorldPoint(plan, person);
    addPerson(scene, x, z, [[.4, .7, .75]], { role: person.label, activity: 'В выделенной зоне ожидания',
      stationary: true, waypoints: [[x, z], [x, z]] });
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
