import { createRandom, pick, range } from '../core/random.js';

export const BASE_COLORS = {
  ground: [0.18, 0.29, 0.22], asphalt: [0.18, 0.21, 0.21], concrete: [0.55, 0.58, 0.57],
  wall: [0.78, 0.82, 0.80], roof: [0.18, 0.25, 0.24], glass: [0.30, 0.62, 0.68]
};

export function makeBlock(position, scale, color, options = {}) {
  return { position, scale, color, yaw: options.yaw || 0, type: options.type || 'block', meta: options.meta || null, editorId: options.editorId, editorKind: options.editorKind, solid: options.solid };
}

export function createBaseScene(config, palette = {}) {
  const colors = { ...BASE_COLORS, ...palette };
  const random = createRandom(`${config.template}:${config.seed}`);
  const scene = {
    config, random, colors, staticObjects: [], solids: [], interactables: [], routes: [], people: [], labels: [],
    spawn: [0, 1.72, config.depth / 2 + 13]
  };
  addShell(scene);
  return scene;
}

function addShell(scene) {
  const { width, depth } = scene.config;
  const { colors } = scene;
  const front = depth / 2;
  const back = -depth / 2;
  const height = 7.5;
  const doorWidth = 5.4;
  const wallThickness = .42;
  scene.staticObjects.push(makeBlock([0, -.35, 0], [width + 34, .6, depth + 40], colors.ground, { type: 'ground' }));
  scene.staticObjects.push(makeBlock([0, -.03, front + 9], [16, .08, 18], colors.asphalt, { type: 'asphalt' }));
  scene.staticObjects.push(makeBlock([0, .01, 0], [width, .12, depth], colors.concrete, { type: 'floor' }));
  scene.staticObjects.push(makeBlock([0, height + .2, 0], [width + .6, .35, depth + .6], colors.roof, { type: 'roof' }));
  const walls = [
    { p: [-width / 2, height / 2, 0], s: [wallThickness, height, depth] },
    { p: [width / 2, height / 2, 0], s: [wallThickness, height, depth] },
    { p: [0, height / 2, back], s: [width, height, wallThickness] },
    { p: [-(width + doorWidth) / 4, height / 2, front], s: [(width - doorWidth) / 2, height, wallThickness] },
    { p: [(width + doorWidth) / 4, height / 2, front], s: [(width - doorWidth) / 2, height, wallThickness] },
    { p: [0, 6.1, front], s: [doorWidth, 2.8, wallThickness], solid: false }
  ];
  walls.forEach(({ p, s, solid = true }, index) => {
    const editorId = `base:wall:${index + 1}`;
    scene.staticObjects.push(makeBlock(p, s, colors.wall, { type: 'wall', editorId, editorKind: 'wall', solid }));
    if (solid) scene.solids.push({ position: p, scale: s, editorId });
  });
  scene.layout = { front, back };
  for (let x = -width / 2 + 5; x <= width / 2 - 5; x += 8) {
    for (let z = back + 4; z <= front - 4; z += 9) {
      scene.staticObjects.push(makeBlock([x, 7.0, z], [3.4, .07, .34], [.86, 1.0, .92], { type: 'light' }));
    }
  }
}

export function addSolid(scene, position, scale, color, options = {}) {
  scene.editorSequence = (scene.editorSequence || 0) + 1;
  const editorId = options.editorId || `base:${options.editorKind || options.type || 'equipment'}:${scene.editorSequence}`;
  const settings = { ...options, editorId, editorKind: options.editorKind || options.type || 'equipment', solid: true };
  scene.staticObjects.push(makeBlock(position, scale, color, settings));
  scene.solids.push({ position, scale, yaw: options.yaw || 0, editorId });
}

export function addPerson(scene, x, z, colors, options = {}) {
  const shirt = pick(scene.random, colors);
  const skin = pick(scene.random, [[.88,.69,.52], [.73,.52,.38], [.55,.37,.27], [.93,.76,.61]]);
  const hair = pick(scene.random, [[.10,.075,.055], [.24,.14,.075], [.48,.31,.13], [.08,.08,.075], [.58,.52,.39]]);
  const pants = pick(scene.random, [[.08,.12,.15], [.12,.18,.24], [.18,.17,.16], [.11,.22,.20]]);
  const angle = range(scene.random, 0, Math.PI * 2);
  const travel = range(scene.random, .65, 1.65);
  const direction = [Math.cos(angle), Math.sin(angle)];
  const fallback = [
    [x - direction[0] * travel, z - direction[1] * travel],
    [x + direction[0] * travel, z + direction[1] * travel]
  ];
  const outbound = options.waypoints?.length > 1 ? options.waypoints : fallback;
  const points = options.oneWay
    ? outbound
    : [...outbound, ...outbound.slice(1, -1).reverse(), outbound[0]];
  const phase = options.phase ?? scene.random();
  const speedRange = options.speedRange || [.28, .52];
  const laneOffset = options.laneOffset ?? range(scene.random, -.13, .13);
  scene.people.push({
    id: scene.people.length + 1,
    role: options.role || 'Сотрудник',
    activity: options.activity || 'Перемещение по объекту',
    points,
    position: [points[0][0], 0, points[0][1]],
    speed: range(scene.random, speedRange[0], speedRange[1]),
    height: range(scene.random, .92, 1.08),
    build: range(scene.random, .90, 1.10),
    stride: range(scene.random, .86, 1.14),
    temperament: range(scene.random, .15, .95),
    baseLaneOffset: laneOffset,
    laneOffset,
    phase,
    shirt,
    skin,
    hair,
    pants,
    accessory: options.role === 'Пассажир' ? 'bag' : ['Врач', 'Медсестра'].includes(options.role) ? 'badge' : options.role ? 'device' : null,
    stopPoints: options.stopPoints || null,
    dwellMin: options.dwellMin ?? .45,
    dwellMax: options.dwellMax ?? 1.4,
    stationary: Boolean(options.stationary),
    pose: options.pose || 'standing',
    allowInsideSolid: Boolean(options.allowInsideSolid)
  });
}

export function addExteriorDetails(scene, accent) {
  const { width, depth } = scene.config;
  const { front, back } = scene.layout;
  scene.staticObjects.push(makeBlock([0, 5.55, front + .28], [9.2, 1.15, .18], [.25, .33, .32], { type: 'sign' }));
  scene.staticObjects.push(makeBlock([0, 5.55, front + .39], [6.5, .54, .10], accent, { type: 'sign' }));
  for (const x of [-width * .32, width * .32]) scene.staticObjects.push(makeBlock([x, 3.8, front + .23], [5.5, 2.2, .10], scene.colors.glass, { type: 'glass' }));
  for (let i = 0; i < 13; i += 1) {
    let x = range(scene.random, -width / 2 - 13, width / 2 + 13);
    const z = range(scene.random, back - 14, front + 18);
    if (Math.abs(x) < 10 && z > front - 2) x += x < 0 ? -11 : 11;
    if (Math.abs(x) < width / 2 + 2 && z > back - 2 && z < front + 2) continue;
    scene.staticObjects.push(makeBlock([x, 1.05, z], [.38, 2.1, .38], [.30, .19, .09]));
    scene.staticObjects.push(makeBlock([x, 2.85, z], [2.0, 2.25, 2.0], pick(scene.random, [[.14,.38,.19], [.18,.46,.23], [.22,.42,.18]])));
  }
}

export { pick, range };
