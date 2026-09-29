import { mat4LookAt, mat4Model, mat4Multiply, mat4Perspective } from './math.js';

const VERTEX_SHADER = `
attribute vec3 aPosition;
attribute vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uViewProjection;
varying vec3 vNormal;
varying vec3 vWorldPosition;
varying vec3 vLocalPosition;
void main() {
  vec4 world = uModel * vec4(aPosition, 1.0);
  vWorldPosition = world.xyz;
  vNormal = normalize(mat3(uModel) * aNormal);
  vLocalPosition = aPosition;
  gl_Position = uViewProjection * world;
}`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform vec3 uColor;
uniform vec3 uCamera;
uniform float uMaterial;
uniform float uEmission;
uniform float uAlpha;
varying vec3 vNormal;
varying vec3 vWorldPosition;
varying vec3 vLocalPosition;
float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
void main() {
  if (uMaterial > 8.5 && uMaterial < 9.5) {
    vec3 ray = normalize(vWorldPosition - uCamera);
    float horizon = smoothstep(-0.18, 0.72, ray.y);
    vec3 lowSky = vec3(.56, .72, .76);
    vec3 highSky = vec3(.12, .30, .39);
    vec3 sky = mix(lowSky, highSky, horizon);
    float sun = pow(max(dot(ray, normalize(vec3(-.45, .62, -.32))), 0.0), 180.0);
    sky += vec3(1.0, .73, .38) * sun * 1.8;
    gl_FragColor = vec4(sky, 1.0);
    return;
  }
  vec3 normal = normalize(vNormal);
  vec3 lightDirection = normalize(vec3(-0.35, 0.85, 0.28));
  vec3 viewDirection = normalize(uCamera - vWorldPosition);
  float diffuse = max(dot(normal, lightDirection), 0.0);
  float hemisphere = mix(.24, .62, normal.y * .5 + .5);
  float light = hemisphere + diffuse * .58;
  vec3 base = uColor;
  float grain = hash(floor(vWorldPosition.xz * 4.0));
  if (uMaterial > 0.5 && uMaterial < 1.5) {
    float gridX = step(0.965, fract(abs(vWorldPosition.x) * 0.5));
    float gridZ = step(0.965, fract(abs(vWorldPosition.z) * 0.5));
    base *= 0.94 + grain * 0.08 - max(gridX, gridZ) * 0.12;
  } else if (uMaterial > 1.5 && uMaterial < 2.5) {
    float seamY = step(0.94, fract(abs(vWorldPosition.y) * 0.5));
    float seamX = step(0.975, fract(abs(vWorldPosition.x) * 0.25));
    base *= 0.96 + grain * 0.05 - max(seamY, seamX) * 0.14;
  } else if (uMaterial > 2.5 && uMaterial < 3.5) {
    float tape = 1.0 - step(0.10, abs(vLocalPosition.x));
    base = mix(base * (0.88 + grain * .12), vec3(.82, .70, .46), tape * .55);
  } else if (uMaterial > 3.5 && uMaterial < 4.5) {
    base *= .82 + grain * .22;
  } else if (uMaterial > 4.5 && uMaterial < 5.5) {
    float stripe = step(.82, fract((vWorldPosition.x + vWorldPosition.y) * 2.0));
    base = mix(base * 1.08, vec3(.72, .92, .94), stripe * .16);
  } else if (uMaterial > 5.5 && uMaterial < 6.5) {
    base *= .80 + grain * .24;
  } else if (uMaterial > 7.5 && uMaterial < 8.5) {
    float warning = step(.5, fract((vWorldPosition.x + vWorldPosition.z) * 1.6));
    base = mix(base, vec3(.12, .13, .12), warning * .28);
  }
  float gloss = uMaterial > 3.5 && uMaterial < 5.5 ? .42 : uMaterial > 6.5 && uMaterial < 7.5 ? .58 : .10;
  float specular = pow(max(dot(normal, normalize(lightDirection + viewDirection)), 0.0), mix(10.0, 44.0, gloss)) * gloss;
  vec3 color = base * light + base * uEmission + vec3(.82, .96, .91) * specular;
  float distanceToCamera = distance(vWorldPosition, uCamera);
  float fog = smoothstep(72.0, 122.0, distanceToCamera);
  vec3 fogColor = vec3(0.54, 0.69, 0.72);
  color = mix(color, fogColor, fog);
  color = pow(max(color, vec3(0.0)), vec3(.92));
  gl_FragColor = vec4(color, uAlpha);
}`;

const CUBE_VERTICES = new Float32Array([
  // front
  -.5,-.5,.5, 0,0,1,  .5,-.5,.5, 0,0,1,  .5,.5,.5, 0,0,1,
  -.5,-.5,.5, 0,0,1,  .5,.5,.5, 0,0,1,  -.5,.5,.5, 0,0,1,
  // back
  .5,-.5,-.5, 0,0,-1,  -.5,-.5,-.5, 0,0,-1,  -.5,.5,-.5, 0,0,-1,
  .5,-.5,-.5, 0,0,-1,  -.5,.5,-.5, 0,0,-1,  .5,.5,-.5, 0,0,-1,
  // left
  -.5,-.5,-.5, -1,0,0,  -.5,-.5,.5, -1,0,0,  -.5,.5,.5, -1,0,0,
  -.5,-.5,-.5, -1,0,0,  -.5,.5,.5, -1,0,0,  -.5,.5,-.5, -1,0,0,
  // right
  .5,-.5,.5, 1,0,0,  .5,-.5,-.5, 1,0,0,  .5,.5,-.5, 1,0,0,
  .5,-.5,.5, 1,0,0,  .5,.5,-.5, 1,0,0,  .5,.5,.5, 1,0,0,
  // top
  -.5,.5,.5, 0,1,0,  .5,.5,.5, 0,1,0,  .5,.5,-.5, 0,1,0,
  -.5,.5,.5, 0,1,0,  .5,.5,-.5, 0,1,0,  -.5,.5,-.5, 0,1,0,
  // bottom
  -.5,-.5,-.5, 0,-1,0,  .5,-.5,-.5, 0,-1,0,  .5,-.5,.5, 0,-1,0,
  -.5,-.5,-.5, 0,-1,0,  .5,-.5,.5, 0,-1,0,  -.5,-.5,.5, 0,-1,0
]);

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
  return shader;
}

function createProgram(gl) {
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
  gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  return program;
}

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = canvas.getContext('webgl', { antialias: true, alpha: false });
    if (!this.gl) throw new Error('WebGL недоступен. Включите аппаратное ускорение браузера.');
    const gl = this.gl;
    const rendererInfo = gl.getExtension('WEBGL_debug_renderer_info');
    const rendererName = String(gl.getParameter(rendererInfo ? rendererInfo.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
    this.softwareRasterizer = /SwiftShader|llvmpipe|software/i.test(rendererName);
    this.program = createProgram(gl);
    this.locations = {
      position: gl.getAttribLocation(this.program, 'aPosition'),
      normal: gl.getAttribLocation(this.program, 'aNormal'),
      model: gl.getUniformLocation(this.program, 'uModel'),
      viewProjection: gl.getUniformLocation(this.program, 'uViewProjection'),
      color: gl.getUniformLocation(this.program, 'uColor'),
      camera: gl.getUniformLocation(this.program, 'uCamera'),
      material: gl.getUniformLocation(this.program, 'uMaterial'),
      emission: gl.getUniformLocation(this.program, 'uEmission')
    };
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, CUBE_VERTICES, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(this.locations.position);
    gl.vertexAttribPointer(this.locations.position, 3, gl.FLOAT, false, 24, 0);
    gl.enableVertexAttribArray(this.locations.normal);
    gl.vertexAttribPointer(this.locations.normal, 3, gl.FLOAT, false, 24, 12);
    this.locations.alpha = gl.getUniformLocation(this.program, 'uAlpha');
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthFunc(gl.LEQUAL);
    gl.disable(gl.CULL_FACE);
    gl.useProgram(this.program);
    this.analytics = false;
    this.heatmapCache = new WeakMap();
  }

  resize(safePlaybackPlan = null) {
    const ratio = Math.min(window.devicePixelRatio || 1, 1.75);
    const requestedWidth = this.canvas.clientWidth * ratio;
    const requestedHeight = this.canvas.clientHeight * ratio;
    // The safe facility scene is often embedded beside the report. Keep its
    // framebuffer bounded so software WebGL remains usable on laptop screens.
    const denseWarehouse = safePlaybackPlan?.warehouseTransport && safePlaybackPlan.robots.length >= 15;
    const pixelBudget = this.softwareRasterizer ? denseWarehouse ? 100000 : 150000 : 1000000;
    const scale = safePlaybackPlan ? Math.min(1, Math.sqrt(pixelBudget / Math.max(1, requestedWidth * requestedHeight))) : 1;
    const width = Math.max(1, Math.floor(requestedWidth * scale));
    const height = Math.max(1, Math.floor(requestedHeight * scale));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
  }

  begin(camera, safePlaybackPlan = null) {
    this.resize(safePlaybackPlan);
    const gl = this.gl;
    gl.clearColor(.54, .69, .72, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const projection = mat4Perspective(Math.PI / 3.05, this.canvas.width / this.canvas.height, .08, 135);
    const cp = Math.cos(camera.pitch);
    const target = [
      camera.position[0] + Math.sin(camera.yaw) * cp,
      camera.position[1] + Math.sin(camera.pitch),
      camera.position[2] - Math.cos(camera.yaw) * cp
    ];
    const view = mat4LookAt(camera.position, target);
    this.viewProjection = mat4Multiply(projection, view);
    gl.uniformMatrix4fv(this.locations.viewProjection, false, this.viewProjection);
    gl.uniform3fv(this.locations.camera, camera.position);
    gl.depthMask(false);
    this.cube(camera.position, [128, 128, 128], [1, 1, 1], 0, 9, 0);
    gl.depthMask(true);
  }

  cube(position, scale, color, yaw = 0, material = 0, emission = 0, alpha = 1) {
    const gl = this.gl;
    gl.uniformMatrix4fv(this.locations.model, false, mat4Model(position, scale, yaw));
    gl.uniform3fv(this.locations.color, color);
    gl.uniform1f(this.locations.material, material);
    gl.uniform1f(this.locations.emission, emission);
    gl.uniform1f(this.locations.alpha, alpha);
    gl.drawArrays(gl.TRIANGLES, 0, 36);
  }

  render(scene, simulation, camera, editorState = null) {
    this.begin(camera, scene.safePlaybackPlan);
    const surfaces = scene.staticObjects.filter(object => ['ground', 'asphalt', 'floor', 'roof'].includes(object.type));
    const opaque = scene.staticObjects.filter(object => !['ground', 'asphalt', 'floor', 'roof', 'glass'].includes(object.type));
    const glass = scene.staticObjects.filter(object => object.type === 'glass');
    surfaces.forEach(object => this.staticObject(object));
    if (scene.safePlaybackPlan) this.contactShadows(opaque.filter(object => ['rack', 'bed', 'seat', 'checkin'].includes(object.type)));
    else this.contactShadows(opaque);
    opaque.forEach(object => this.staticObject(object));
    this.gl.depthMask(false);
    glass.forEach(object => this.staticObject(object, .34));
    this.gl.depthMask(true);
    if (this.analytics) this.heatmap(simulation);
    if (!scene.safePlaybackPlan) this.routeGuides(simulation);
    simulation.robots.forEach(robot => { if (robot.activeTask && robot.cargoStage === 'waiting') this.waitingCargo(robot); });
    simulation.people.forEach(person => this.person(person));
    simulation.deliveredCargo.forEach(cargo => this.deliveredCargo(cargo));
    simulation.robots.forEach(robot => this.robot(robot));
    if (editorState) this.editorOverlay(editorState);
    if (!scene.safePlaybackPlan) this.dust(scene, camera);
  }

  staticObject(object, alpha = 1) {
    const material = materialFor(object.type);
    const emission = object.type === 'light' || object.type === 'sign' ? .72 : object.type === 'charger' ? .24 : 0;
    const userBuilt = object.editorId?.startsWith('user:');
    if (!((userBuilt || object.meta?.detailed) && ['rack', 'fence'].includes(object.type))) this.cube(object.position, object.scale, object.color, object.yaw, material, emission, alpha);
    if (object.type === 'cargo' && !object.meta?.onRack && (userBuilt || object.editorKind !== 'rack')) this.cargoDetails(object);
    if (object.type === 'charger' && !object.meta?.compact) this.chargerDetails(object);
    if (object.type === 'station' || object.type === 'checkin' || object.type === 'reception') this.stationDetails(object);
    if ((userBuilt || object.meta?.detailed) && object.type === 'rack') this.rackDetails(object);
    if (userBuilt && object.type === 'fence') this.fenceDetails(object);
    if (userBuilt && object.type === 'wall') this.wallDetails(object);
    if (userBuilt && object.type === 'decor') this.crateDetails(object);
    if (object.type === 'bed') this.bedDetails(object);
  }

  detailPart(object, offset, scale, color, material = 4, emission = 0, alpha = 1) {
    const yaw = object.yaw || 0;
    const ox = offset[0] * Math.cos(yaw) + offset[2] * Math.sin(yaw);
    const oz = -offset[0] * Math.sin(yaw) + offset[2] * Math.cos(yaw);
    this.cube([object.position[0] + ox, object.position[1] + offset[1], object.position[2] + oz], scale, color, yaw, material, emission, alpha);
  }

  contactShadows(objects) {
    const shadowTypes = new Set(['rack', 'cargo', 'station', 'charger', 'checkin', 'seat', 'baggage', 'bed', 'reception', 'supply', 'fence', 'decor']);
    this.gl.depthMask(false);
    objects.forEach(object => {
      if (!shadowTypes.has(object.type)) return;
      if (object.editorKind === 'rack' && object.type !== 'rack') return;
      if (object.meta?.onRack || (['charger', 'rack'].includes(object.type) && object.meta?.compact)) return;
      const width = Math.min(object.scale[0] * 1.08, 8); const depth = Math.min(object.scale[2] * 1.08, 8);
      this.cube([object.position[0] + .09, .078, object.position[2] + .12], [width, .008, depth], [.015, .025, .022], object.yaw || 0, 0, 0, .24);
    });
    this.gl.depthMask(true);
  }

  cargoDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2];
    const dark = object.color.map(value => value * .62);
    this.detailPart(object, [0, -sy / 2 - .045, 0], [sx * 1.04, .09, sz * 1.04], [.38, .23, .11], 4);
    for (const side of [-1, 1]) this.detailPart(object, [side * sx * .34, -sy / 2 - .105, 0], [sx * .12, .10, sz * .92], [.24, .15, .08], 4);
    this.detailPart(object, [0, sy * .18, sz / 2 + .012], [sx * .72, sy * .055, .018], dark, 4);
  }

  chargerDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2];
    this.detailPart(object, [0, sy / 2 + .018, 0], [sx * .68, .025, sz * .68], [.14, .96, .65], 7, .42);
    this.detailPart(object, [0, .34, -sz * .39], [sx * .55, .62, .08], [.08, .22, .19], 4);
    this.detailPart(object, [0, .39, -sz * .435], [sx * .25, .18, .018], [.35, 1.0, .72], 7, .75);
  }

  stationDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2];
    this.detailPart(object, [0, sy / 2 + .075, 0], [sx * 1.02, .15, sz * 1.02], [.12, .18, .17], 4);
    this.detailPart(object, [0, sy * .68, -sz * .32], [Math.min(1.1, sx * .3), .55, .08], [.08, .18, .19], 4);
    this.detailPart(object, [0, sy * .69, -sz * .37], [Math.min(.78, sx * .22), .30, .018], [.22, .82, .70], 7, .28);
  }

  rackDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2];
    const frame = [.10, .16, .17]; const beam = [.94, .49, .10];
    if (object.meta?.compact) {
      for (const x of [-sx / 2 + .06, sx / 2 - .06]) this.detailPart(object, [x, 0, -sz / 2 + .06], [.11, sy, .11], frame, 4);
      this.detailPart(object, [0, -sy / 2 + 1.3, 0], [sx, .09, sz], frame, 4);
      this.detailPart(object, [0, sy / 2 - .29, sz / 2], [sx + .12, .13, .10], beam, 8);
      return;
    }
    for (const x of [-sx / 2 + .06, sx / 2 - .06]) for (const z of [-sz / 2 + .06, sz / 2 - .06]) this.detailPart(object, [x, 0, z], [.11, sy, .11], frame, 4);
    for (let level = -sy / 2 + .55; level < sy / 2; level += Math.max(.75, sy / 4)) {
      this.detailPart(object, [0, level, 0], [sx, .09, sz], frame, 4);
      for (const z of [-sz / 2, sz / 2]) this.detailPart(object, [0, level + .06, z], [sx + .12, .13, .10], beam, 8);
    }
  }

  wallDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2];
    const alongX = sx >= sz;
    const trim = [.25, .34, .32];
    this.detailPart(object, [0, -sy / 2 + .09, 0], alongX ? [sx * 1.01, .18, sz * 1.08] : [sx * 1.08, .18, sz * 1.01], trim, 4);
    this.detailPart(object, [0, sy / 2 - .06, 0], alongX ? [sx * 1.01, .11, sz * 1.05] : [sx * 1.05, .11, sz * 1.01], [.54, .64, .61], 4);
  }

  fenceDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2]; const alongX = sx >= sz;
    const length = alongX ? sx : sz;
    const posts = Math.max(2, Math.ceil(length / 1.5));
    for (let index = 0; index < posts; index += 1) {
      const offset = -length / 2 + index * length / (posts - 1);
      this.detailPart(object, alongX ? [offset, 0, 0] : [0, 0, offset], [.10, sy, .10], [.18, .22, .21], 4);
    }
    for (const y of [-sy * .23, sy * .23]) this.detailPart(object, [0, y, 0], alongX ? [sx, .10, .10] : [.10, .10, sz], object.color, 8);
  }

  crateDetails(object) {
    const sx = object.scale[0]; const sy = object.scale[1]; const sz = object.scale[2]; const edge = [.12, .22, .20];
    for (const x of [-sx / 2, sx / 2]) for (const z of [-sz / 2, sz / 2]) this.detailPart(object, [x, 0, z], [.055, sy * 1.02, .055], edge, 4);
    this.detailPart(object, [0, sy / 2, 0], [sx * .92, .055, sz * .92], [.42, .70, .60], 4);
  }

  bedDetails(object) {
    this.detailPart(object, [0, -.33, 0], [object.scale[0] * .72, .10, object.scale[2] * .72], [.18, .27, .26], 4);
    for (const x of [-.36, .36]) for (const z of [-.72, .72]) this.detailPart(object, [x, -.48, z], [.08, .32, .08], [.09, .12, .12], 4);
  }

  editorOverlay(state) {
    if (state.hovered && state.hovered.kind !== 'robot') this.cube(state.hovered.position, state.hovered.scale.map(value => value + .07), [.35, .92, .72], state.hovered.yaw, 7, .55, .28);
    if (state.hovered?.kind === 'robot') this.cube([state.hovered.position[0], .06, state.hovered.position[2]], [state.hovered.scale[0] + .22, .035, state.hovered.scale[2] + .22], [.35, .92, .72], 0, 7, .65, .9);
    if (state.selected && state.selected.kind !== 'robot') {
      const scale = state.selected.scale; const p = state.selected.position; const color = [.98, .78, .18];
      this.cube(p, [scale[0] + .12, .045, scale[2] + .12], color, state.selected.yaw, 7, .75, .9);
      this.cube([p[0], p[1] + scale[1] / 2 + .05, p[2]], [scale[0] + .12, .045, scale[2] + .12], color, state.selected.yaw, 7, .75, .9);
    }
    if (state.selected?.kind === 'robot') {
      const p = state.selected.position; const scale = state.selected.scale;
      this.cube([p[0], .075, p[2]], [scale[0] + .34, .04, scale[2] + .34], [.98, .78, .18], 0, 7, .8, .95);
      this.cube([p[0], 1.55, p[2]], [.08, 1.8, .08], [.98, .78, .18], 0, 7, .8, .75);
    }
    if (state.preview) {
      const color = state.preview.valid ? [.20, .94, .54] : [1.0, .18, .12];
      this.gl.depthMask(false);
      this.cube(state.preview.position, state.preview.scale, color, state.preview.yaw || 0, 7, .45, .42);
      this.gl.depthMask(true);
    }
  }

  routeGuides(simulation) {
    simulation.robots.forEach((robot, routeIndex) => {
      const points = robot.route.points;
      const color = robot.color.map(value => Math.min(1, value * 1.25));
      if (this.analytics) for (let segment = 0; segment < points.length - 1; segment += 1) {
        const a = points[segment]; const b = points[segment + 1];
        const dx = b[0] - a[0]; const dz = b[1] - a[1]; const length = Math.hypot(dx, dz);
        const yaw = Math.atan2(dx, dz);
        for (let distance = 1.0 + (routeIndex % 3) * .32; distance < length; distance += 2.4) {
          const amount = distance / length;
          this.cube([a[0] + dx * amount, .075, a[1] + dz * amount], [.10, .018, .72], color, yaw, 7, .10);
        }
      }
      const pickup = points[robot.route.pickupWaypoint ?? 2];
      const drop = robot.route.dropPosition || points[robot.route.dropWaypoint ?? 4];
      this.zoneMarker(pickup, [.20, .88, .58]);
      this.zoneMarker(drop, [1.0, .62, .12]);
      const pulse = .9 + Math.sin(performance.now() * .006 + robot.id) * .25;
      this.cube([robot.position[0], .105, robot.position[2]], [.42, .025, .42], color, robot.yaw, 7, pulse);
      if (this.analytics && robot.reservedPosition) {
        const reservationColor = robot.reservationBlocked ? [.98, .24, .14] : [.22, .92, .58];
        const markerSize = robot.reservationBlocked ? .82 : 1.55;
        this.cube([robot.reservedPosition[0], robot.reservationBlocked ? .105 : .075, robot.reservedPosition[1]], [markerSize, .018, markerSize], reservationColor, 0, 7, robot.reservationBlocked ? .28 : .14);
      }
      if (this.analytics) this.sensorCorridor(robot);
      if (robot.detourPath?.length) this.dynamicRoute(robot);
    });
  }

  dynamicRoute(robot) {
    const points = [[robot.position[0], robot.position[2]], ...robot.detourPath];
    for (let index = 0; index < points.length - 1; index += 1) {
      const a = points[index]; const b = points[index + 1];
      const dx = b[0] - a[0]; const dz = b[1] - a[1]; const length = Math.hypot(dx, dz);
      const yaw = Math.atan2(dx, dz);
      for (let distance = .25; distance < length; distance += .48) {
        const amount = distance / length;
        this.cube([a[0] + dx * amount, .115, a[1] + dz * amount], [.08, .025, .30], [.18, .86, 1.0], yaw, 7, .48, .82);
      }
    }
  }

  sensorCorridor(robot) {
    const color = robot.blockedByHuman || robot.blockedByRobot || robot.reservationBlocked ? [.96, .24, .12] : robot.avoidingHuman ? [.16, .62, 1.0] : [.28, .90, .64];
    for (let step = 1; step <= 3; step += 1) {
      const distance = step * .62 + .42;
      const x = robot.position[0] + Math.sin(robot.yaw) * distance;
      const z = robot.position[2] + Math.cos(robot.yaw) * distance;
      this.cube([x, .11, z], [.44 + step * .18, .014, .42], color, robot.yaw, 7, .16);
    }
  }

  heatmap(simulation) {
    let cells = this.heatmapCache.get(simulation);
    if (!cells) {
      const grid = new Map();
      simulation.robots.forEach(robot => {
        const points = robot.route.points;
        for (let segment = 0; segment < points.length - 1; segment += 1) {
          const a = points[segment]; const b = points[segment + 1];
          const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
          for (let distance = 0; distance <= length; distance += .8) {
            const amount = length ? distance / length : 0;
            const x = Math.round((a[0] + (b[0] - a[0]) * amount) / 1.6);
            const z = Math.round((a[1] + (b[1] - a[1]) * amount) / 1.6);
            const key = `${x}:${z}`;
            grid.set(key, (grid.get(key) || 0) + 1);
          }
        }
      });
      const max = Math.max(...grid.values(), 1);
      cells = [...grid.entries()].map(([key, count]) => {
        const [x, z] = key.split(':').map(Number);
        return { x: x * 1.6, z: z * 1.6, intensity: count / max };
      });
      this.heatmapCache.set(simulation, cells);
    }
    cells.forEach(cell => {
      const color = cell.intensity > .66 ? [.92, .22, .12] : cell.intensity > .34 ? [.94, .70, .12] : [.12, .70, .49];
      this.cube([cell.x, .045, cell.z], [1.52, .012, 1.52], color, 0, 7, .10 + cell.intensity * .15);
    });
  }

  setAnalytics(enabled) {
    this.analytics = Boolean(enabled);
  }

  project(position) {
    if (!this.viewProjection) return null;
    const [x, y, z] = position; const m = this.viewProjection;
    const clipX = m[0] * x + m[4] * y + m[8] * z + m[12];
    const clipY = m[1] * x + m[5] * y + m[9] * z + m[13];
    const clipZ = m[2] * x + m[6] * y + m[10] * z + m[14];
    const clipW = m[3] * x + m[7] * y + m[11] * z + m[15];
    if (clipW <= .05) return null;
    const nx = clipX / clipW; const ny = clipY / clipW; const nz = clipZ / clipW;
    if (Math.abs(nx) > 1.08 || Math.abs(ny) > 1.08 || nz < -1 || nz > 1) return null;
    return { x: (nx * .5 + .5) * this.canvas.clientWidth, y: (-ny * .5 + .5) * this.canvas.clientHeight, depth: nz };
  }

  zoneMarker(point, color) {
    if (!point) return;
    const [x, z] = point;
    this.cube([x - .72, .09, z], [.12, .025, 1.55], color, 0, 7, .28);
    this.cube([x + .72, .09, z], [.12, .025, 1.55], color, 0, 7, .28);
    this.cube([x, .09, z - .72], [1.55, .025, .12], color, 0, 7, .28);
    this.cube([x, .09, z + .72], [1.55, .025, .12], color, 0, 7, .28);
  }

  dust(scene, camera) {
    const halfW = scene.config.width / 2;
    const halfD = scene.config.depth / 2;
    if (Math.abs(camera.position[0]) > halfW || Math.abs(camera.position[2]) > halfD || camera.position[1] > 7.4) return;
    const time = performance.now() * .00008;
    for (let i = 0; i < 20; i += 1) {
      const angle = i * 2.399 + time * (i % 3 + 1);
      const radius = 2.5 + (i * 1.73) % 11;
      const x = camera.position[0] + Math.cos(angle) * radius;
      const z = camera.position[2] + Math.sin(angle) * radius;
      const y = .5 + ((i * 1.91 + time * 12) % 5.8);
      this.cube([x, y, z], [.025, .025, .025], [.82, 1.0, .91], 0, 7, .55);
    }
  }

  robot(robot) {
    const [x, y, z] = robot.position;
    const yaw = robot.yaw;
    const part = (offset, scale, color, material = 4, emission = 0) => {
      const ox = offset[0] * Math.cos(yaw) + offset[2] * Math.sin(yaw);
      const oz = -offset[0] * Math.sin(yaw) + offset[2] * Math.cos(yaw);
      this.cube([x + ox, y + offset[1], z + oz], scale, color, yaw, material, emission);
    };
    if (robot.visualFootprint) {
      // All physical parts of this explicitly illustrative v2 glyph stay inside its declared footprint.
      const { width, length } = robot.visualFootprint;
      const waiting = robot.mode === 'idle';
      const color = waiting ? [.30, .43, .47] : [.10, .69, .55];
      part([0, 0, 0], [width, .3, length], color);
      part([0, robot.kind === 'medical' ? .53 : .27, 0], [width * .70, robot.kind === 'medical' ? .8 : .24, length * .65],
        robot.kind === 'medical' ? [.71, .90, .86] : robot.carrying ? [.81, .61, .28] : [.12, .29, .32]);
      part([0, robot.kind === 'medical' ? 1.04 : .46, 0], [.10, .10, .10], waiting ? [.96, .67, .10] : [.25, .95, .71], 7, .5);
      return;
    }
    const charging = robot.mode === 'charging';
    const fault = robot.mode === 'fault';
    const type = robot.robotType || 'pallet-amr';
    const bodyColor = fault ? [.58, .10, .08] : charging ? [.08, .56, .65] : robot.mode === 'idle' ? [.26, .34, .34] : robot.blockedByHuman || robot.blockedByRobot ? [.86, .48, .10] : robot.avoidingHuman ? [.12, .48, .82] : robot.color;
    const chargePulse = .35 + Math.sin(performance.now() * .008 + robot.id) * .18;
    if (charging) {
      this.cube([x, .055, z], [robot.radius * 2.45, .025, robot.radius * 2.65], [.12, .78, .88], yaw, 7, chargePulse);
      this.cube([x, .075, z], [robot.radius * 2.05, .018, robot.radius * 2.25], [.06, .18, .20], yaw, 7, .2);
    } else if (fault) {
      const faultPulse = .45 + Math.sin(performance.now() * .014 + robot.id) * .30;
      this.cube([x, .055, z], [1.48, .025, 1.72], [.92, .12, .08], yaw, 7, faultPulse);
    } else this.cube([x, .08, z], [robot.radius * 1.92, .035, robot.radius * 2.35], [.08, .10, .10], yaw, 0, 0, .68);
    const beaconColor = fault ? [.92, .12, .08] : robot.mode === 'idle' ? [.95, .68, .12] : [.27, .86, .64];
    const pulse = .55 + Math.sin(performance.now() * .006 + robot.id) * .25;
    const operationProgress = robot.operationProgress || 0;
    const lift = robot.operationType === 'pickup' ? operationProgress : robot.operationType === 'drop' ? 1 - operationProgress : robot.carrying ? 1 : 0;
    if (type === 'forklift') {
      part([0, 0, 0], [1.12, .36, 1.30], bodyColor);
      part([0, .57, -.28], [.78, .92, .62], [.12, .20, .20]);
      part([0, .66, .05], [.64, .48, .08], [.28, .58, .62], 5);
      for (const side of [-1, 1]) {
        part([side * .39, .66, .52], [.09, 1.45, .10], [.10, .13, .13]);
        part([side * .28, -.10 + lift * .50, 1.0], [.11, .09, 1.05], [.16, .18, .17]);
        part([side * .50, -.06, -.34], [.20, .34, .38], [.025, .035, .035]);
      }
      part([0, 1.10, -.28], [.15, .18, .15], beaconColor, 7, pulse);
      if (robot.carrying) {
        part([0, .20 + lift * .50, .92], [.86, .11, .78], [.48, .30, .14]);
        part([0, .49 + lift * .50, .92], [.76, .46, .68], [.72, .50, .25], 2);
      }
    } else if (type === 'tow-amr' || type === 'baggage-tug') {
      part([0, 0, .05], [1.05, .36, 1.28], bodyColor);
      part([0, .35, .28], [.68, .50, .54], [.08, .18, .20]);
      part([0, .40, .58], [.52, .24, .08], [.30, .62, .68], 5);
      part([0, .02, -.78], [.16, .13, .42], [.12, .14, .14]);
      for (const side of [-1, 1]) part([side * .50, -.07, .0], [.16, .30, .38], [.025, .035, .035]);
      part([0, .72, .18], [.13, .18, .13], beaconColor, 7, pulse);
      if (robot.carrying) {
        const coupling = robot.operationType === 'pickup' ? operationProgress : 1;
        part([0, .64, -.55 + coupling * .37], [.82, .56, .72], robot.kind === 'baggage' ? [.42, .18, .15] : [.58, .43, .22], 2);
      }
    } else if (type === 'medical-cart') {
      part([0, -.04, 0], [.72, .27, .82], [.06, .18, .17]);
      part([0, .58, 0], [.66, 1.08, .68], bodyColor);
      const doorOpen = robot.operationType === 'drop' || (robot.facilityPose && robot.operationType === 'pickup') ? Math.sin(operationProgress * Math.PI) : 0;
      part([-.17 - doorOpen * .16, .58, .355], [.30, .82, .035], [.78, .90, .87]);
      part([.17 + doorOpen * .16, .58, .355], [.30, .82, .035], [.78, .90, .87]);
      part([0, .70, .35], [.42, .38, .035], [.15, .42, .40], 7, .18);
      part([0, 1.18, 0], [.48, .10, .48], [.82, .94, .90]);
      part([0, 1.32, 0], [.12, .14, .12], beaconColor, 7, pulse);
      for (const side of [-1, 1]) part([side * .30, -.14, .22], [.13, .22, .22], [.025, .035, .035]);
      if (robot.facilityPose && robot.carrying) for (let shelf = 0; shelf < 3; shelf += 1)
        part([0, .28 + shelf * .28, .38], [.48, .07, .22], [.96,.72,.38], 2);
      if (robot.facilityPose && robot.operationType) part([0, .5, .45 + doorOpen * .45], [.5, .1, .35], [.96,.72,.38], 2);
    } else if (type === 'cleaning-robot') {
      part([0, -.03, 0], [1.02, .24, 1.18], bodyColor);
      part([0, .27, -.05], [.72, .42, .70], [.12,.30,.31]);
      part([0, .52, -.12], [.45, .25, .45], bodyColor);
      part([0, .72, -.12], [.11,.15,.11], beaconColor, 7, pulse);
      part([0, -.17, .26], [1.18,.05,.52], [.16,.72,.62], 7, .22);
      if (robot.facilityPose?.cleaning) {
        const phase = robot.facilityPose.progress * Math.PI * 40;
        part([Math.sin(phase) * .3, -.2, .55], [.45,.045,.45], [.35,.95,.75], 7, .45);
        part([0, -.32, -.9], [1.25,.025,1.2], [.12,.68,.62], 7, .25);
      }
    } else if (type === 'palletizer-cell') {
      const arm = Math.sin((robot.operationProgress || 0) * Math.PI * 2);
      part([0, -.05, 0], [1.15,.18,1.15], [.20,.23,.22]);
      part([0, .52, 0], [.30,1.05,.30], bodyColor);
      part([arm * .22, 1.05, .18], [.28,.82,.28], bodyColor, 4);
      part([arm * .42, 1.43, .36], [.72,.24,.24], bodyColor, 4);
      part([arm * .75, 1.35, .55], [.22,.20,.22], [.16,.18,.18]);
      part([0, .18, -.42], [.12,.13,.12], beaconColor, 7, pulse);
    } else if (type === 'service-robot') {
      part([0, -.05, 0], [.70, .26, .72], bodyColor);
      part([0, .39, 0], [.42, .68, .42], [.18, .40, .42]);
      part([0, .82, .04], [.58, .34, .46], bodyColor);
      part([-.14, .86, .28], [.08, .07, .035], [.70, 1.0, .91], 7, .65);
      part([.14, .86, .28], [.08, .07, .035], [.70, 1.0, .91], 7, .65);
      part([0, 1.05, .02], [.10, .13, .10], beaconColor, 7, pulse);
      if (robot.carrying) part([0, .62, .26], [.34, .24, .25], [.80, .88, .84]);
    } else {
      part([0, 0, 0], [1.05, .38, 1.35], bodyColor);
      part([0, .27, 0], [.72, .18, .75], [.07, .16, .16]);
      for (const side of [-1, 1]) {
        part([side * .52, -.07, .38], [.13, .28, .34], [.035, .045, .045]);
        part([side * .52, -.07, -.38], [.13, .28, .34], [.035, .045, .045]);
      }
      part([0, .48, .25], [.17, .24, .17], beaconColor, 4);
      part([0, .62, .25], [.09, .09, .09], fault ? [1.0, .18, .10] : [.68, 1.0, .86], 7, fault ? .9 : pulse);
      if (robot.carrying) {
        if (robot.kind === 'baggage') part([0, .68, .12], [.72, .54, .82], [.48, .16, .12], 2);
        else {
          part([0, .56, .12], [.88, .12, 1.02], [.48, .30, .14], 4);
          part([0, .86, .12], [.76, .48, .85], [.72, .50, .25], 2);
        }
      }
    }
    part([-.28, .03, .66], [.15, .09, .04], [.75, 1.0, .88], 7, .75);
    part([.28, .03, .66], [.15, .09, .04], [.75, 1.0, .88], 7, .75);
    const batteryRatio = Math.max(.04, Math.min(1, robot.battery / 100));
    const batteryColor = batteryRatio < .31 ? [.96, .25, .12] : batteryRatio < .56 ? [.96, .68, .10] : [.24, .92, .55];
    part([0, .405, -.34], [.82, .055, .16], [.025, .06, .06], 4);
    part([-.39 + batteryRatio * .39, .408, -.342], [.76 * batteryRatio, .06, .17], batteryColor, 7, charging ? .7 + chargePulse : .25);
  }

  waitingCargo(robot) {
    const point = robot.route.points[robot.route.pickupWaypoint ?? 2];
    if (!point) return;
    const x = point[0] + ((robot.id % 3) - 1) * .32;
    const z = point[1] + (robot.id % 2 ? .28 : -.28);
    if (robot.robotType === 'forklift' || robot.robotType === 'pallet-amr') {
      this.cube([x, .10, z], [.82, .12, .76], [.48, .30, .14], 0, 4);
      this.cube([x, .39, z], [.72, .45, .66], [.72, .50, .25], 0, 2);
    } else if (robot.kind === 'baggage') {
      this.cube([x, .28, z], [.62, .46, .68], [.42, .18, .15], 0, 2);
      this.cube([x, .55, z], [.24, .10, .08], [.08, .12, .13], 0, 4);
    } else if (robot.kind === 'medical') {
      this.cube([x, .26, z], [.48, .48, .48], [.82, .90, .87]);
      this.cube([x, .52, z], [.26, .055, .26], [.16, .68, .55], 0, 7, .22);
    } else {
      this.cube([x, .30, z], [.72, .52, .68], [.58, .43, .22], 0, 2);
    }
  }

  person(person) {
    if (person.pose === 'lying') { this.lyingPerson(person); return; }
    if (person.pose === 'seated') { this.seatedPerson(person); return; }
    const [x, , z] = person.position;
    const height = person.height || 1;
    const build = person.build || 1;
    const swing = person.walking ? Math.sin(person.walkPhase) * .14 : 0;
    const gesture = !person.walking && person.pause > 0 ? Math.sin(person.actionPhase) * .12 : 0;
    const part = (offset, scale, color, yaw = person.yaw, material = 0, emission = 0) => {
      const ox = offset[0] * Math.cos(yaw) + offset[2] * Math.sin(yaw);
      const oz = -offset[0] * Math.sin(yaw) + offset[2] * Math.cos(yaw);
      this.cube([x + ox, offset[1] * height, z + oz], [scale[0] * build, scale[1] * height, scale[2] * build], color, yaw, material, emission);
    };
    const blocked = person.blockedByPerson || person.blockedByRobot || person.blockedByObstacle;
    this.cube([x, .078, z], [.52 * build, .018, .44 * build], blocked ? [.56, .15, .10] : [.04, .06, .055], person.yaw, blocked ? 7 : 0, blocked ? .18 : 0, blocked ? .78 : .34);
    part([0, 1.03, 0], [.46, .88, .32], person.shirt);
    part([0, 1.61, 0], [.36, .36, .36], person.skin || [.76, .58, .43]);
    part([0, 1.79, -.015], [.37, .12, .37], person.hair || [.12, .08, .05]);
    part([-.095, 1.66, .19], [.065, .065, .025], [.06, .075, .075]);
    part([.095, 1.66, .19], [.065, .065, .025], [.06, .075, .075]);
    part([0, 1.58, .205], [.055, .065, .035], [.66, .45, .34]);
    part([0, 1.49, .195], [.13, .045, .025], [.48, .14, .15]);
    part([-.14, .38, swing], [.15, .66, .17], person.pants || [.10, .15, .18]);
    part([.14, .38, -swing], [.15, .66, .17], person.pants || [.10, .15, .18]);
    part([-.31, 1.08 + gesture, -swing], [.13, .64, .14], person.shirt);
    part([.31, 1.08 - gesture, swing], [.13, .64, .14], person.shirt);
    part([-.31, .73 + gesture, -swing], [.14, .16, .15], person.skin || [.76, .58, .43]);
    part([.31, .73 - gesture, swing], [.14, .16, .15], person.skin || [.76, .58, .43]);
    if (person.accessory === 'bag') {
      part([.37, .82, -.04], [.28, .42, .20], [.22, .13, .08], person.yaw, 4);
    } else if (person.accessory === 'badge') {
      part([.12, 1.22, .18], [.10, .14, .025], [.82, 1.0, .94], person.yaw, 7, .18);
    } else if (person.accessory === 'device') {
      part([.31, .86 - gesture, .11], [.16, .24, .055], [.08, .18, .22], person.yaw, 7, .12);
    }
  }

  lyingPerson(person) {
    const [x, , z] = person.position; const yaw = person.yaw || 0;
    const part = (offset, scale, color, material = 0) => {
      const ox = offset[0] * Math.cos(yaw) + offset[2] * Math.sin(yaw);
      const oz = -offset[0] * Math.sin(yaw) + offset[2] * Math.cos(yaw);
      this.cube([x + ox, offset[1], z + oz], scale, color, yaw, material);
    };
    part([0, 1.03, .16], [.56, .22, 1.18], [.66, .82, .80]);
    part([0, 1.14, -.58], [.38, .30, .38], person.skin || [.76, .58, .43]);
    part([0, 1.23, -.68], [.39, .11, .30], person.hair || [.12, .08, .05]);
    part([0, 1.17, .36], [.50, .10, .72], [.80, .91, .88]);
  }

  seatedPerson(person) {
    const [x, , z] = person.position; const yaw = person.yaw || 0;
    const part = (offset, scale, color, material = 0, emission = 0) => {
      const ox = offset[0] * Math.cos(yaw) + offset[2] * Math.sin(yaw);
      const oz = -offset[0] * Math.sin(yaw) + offset[2] * Math.cos(yaw);
      this.cube([x + ox, offset[1], z + oz], scale, color, yaw, material, emission);
    };
    this.cube([x, .078, z], [.48, .018, .45], [.04, .06, .055], yaw, 0, 0, .3);
    part([0, .78, 0], [.46, .70, .34], person.shirt);
    part([0, 1.27, .02], [.36, .36, .36], person.skin || [.76, .58, .43]);
    part([0, 1.45, 0], [.37, .11, .37], person.hair || [.12, .08, .05]);
    for (const side of [-1, 1]) {
      part([side * .14, .37, .22], [.15, .52, .17], person.pants || [.10, .15, .18]);
      part([side * .29, .82, .20], [.12, .52, .13], person.shirt);
    }
    part([0, .51, -.12], [.58, .08, .58], [.10, .15, .15], 4);
    part([0, .24, -.12], [.10, .52, .10], [.08, .11, .11], 4);
  }

  deliveredCargo(cargo) {
    const [x, y, z] = cargo.position;
    if (cargo.kind === 'baggage') {
      this.cube([x, y, z], [.62, .48, .76], cargo.color, 0, 2);
      this.cube([x, y + .31, z], [.28, .12, .08], [.10, .13, .13], 0, 4);
    } else if (cargo.kind === 'medical') {
      this.cube([x, y, z], [.62, .48, .62], cargo.color);
      this.cube([x, y + .28, z], [.28, .04, .28], [.16, .66, .53], 0, 7, .2);
    } else {
      this.cube([x, y - .27, z], [.68, .12, .68], [.48, .30, .14], 0, 4);
      this.cube([x, y, z], [.58, .48, .58], cargo.color, 0, 3);
    }
  }
}

function materialFor(type) {
  if (type === 'floor') return 1;
  if (type === 'wall' || type === 'roof') return 2;
  if (type === 'cargo') return 3;
  if (type === 'metal' || type === 'rack') return 4;
  if (type === 'glass') return 5;
  if (type === 'ground' || type === 'asphalt') return 6;
  if (type === 'light' || type === 'sign') return 7;
  if (type === 'safety' || type === 'station') return 8;
  return 0;
}
