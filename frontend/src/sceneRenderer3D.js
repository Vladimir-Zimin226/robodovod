import { decodeGlb } from '../../robcraft/src/core/glb-model.js';
import { mat4LookAt, mat4Model, mat4Multiply, mat4Perspective } from '../../robcraft/src/core/math.js';
import { worldToGltf } from './sceneModel.js';

const VERTEX = `
attribute vec3 aPosition;
attribute vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uViewProjection;
varying vec3 vPosition;
varying vec3 vNormal;
void main() {
  vec4 world = uModel * vec4(aPosition, 1.0);
  vPosition = world.xyz;
  vNormal = normalize(mat3(uModel) * aNormal);
  gl_Position = uViewProjection * world;
}`;

const FRAGMENT = `
precision highp float;
varying vec3 vPosition;
varying vec3 vNormal;
uniform vec3 uColor;
uniform vec3 uCamera;
uniform float uMetallic;
uniform float uRoughness;
uniform float uEmission;
uniform float uAlpha;
uniform float uFloor;
const float PI = 3.14159265;
void main() {
  vec3 base = uColor;
  if (uFloor > .5) {
    float tile = max(step(.985, fract(abs(vPosition.x) / 5.0)), step(.985, fract(abs(vPosition.z) / 5.0)));
    base *= 1.0 - .10 * tile;
  }
  vec3 n = normalize(vNormal);
  vec3 v = normalize(uCamera - vPosition);
  vec3 l = normalize(vec3(-.42, .84, .33));
  vec3 h = normalize(v + l);
  float ndl = max(dot(n, l), 0.0);
  float ndv = max(dot(n, v), 0.001);
  float ndh = max(dot(n, h), 0.0);
  float vdh = max(dot(v, h), 0.0);
  float a = max(.06, uRoughness * uRoughness);
  float a2 = a * a;
  float d = a2 / max(PI * pow(ndh * ndh * (a2 - 1.0) + 1.0, 2.0), .001);
  float k = pow(uRoughness + 1.0, 2.0) / 8.0;
  float g = ndv / (ndv * (1.0 - k) + k) * ndl / (ndl * (1.0 - k) + k);
  vec3 f0 = mix(vec3(.04), base, uMetallic);
  vec3 f = f0 + (1.0 - f0) * pow(1.0 - vdh, 5.0);
  vec3 diffuse = (1.0 - f) * (1.0 - uMetallic) * base / PI;
  vec3 specular = d * g * f / max(4.0 * ndl * ndv, .001);
  vec3 color = base * .38 + (diffuse + specular) * ndl * 2.4 + base * uEmission;
  color = color / (color + vec3(1.0));
  color = pow(color, vec3(1.0 / 2.2));
  gl_FragColor = vec4(color, uAlpha);
}`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
  return shader;
}

function meshBounds(groups) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const group of groups) for (let at = 0; at < group.vertices.length; at += 6) {
    for (let axis = 0; axis < 3; axis += 1) {
      min[axis] = Math.min(min[axis], group.vertices[at + axis]);
      max[axis] = Math.max(max[axis], group.vertices[at + axis]);
    }
  }
  return { min, max, size: max.map((value, axis) => value - min[axis]) };
}

export function convertBundledMesh(groups) {
  const converted = groups.map((group) => {
    const vertices = new Float32Array(group.vertices.length);
    for (let at = 0; at < vertices.length; at += 6) {
      vertices.set(worldToGltf(group.vertices.subarray(at, at + 3)), at);
      vertices.set(worldToGltf(group.vertices.subarray(at + 3, at + 6)), at + 3);
    }
    return { ...group, vertices };
  });
  return { groups: converted, bounds: meshBounds(converted) };
}

export function objectMeshScale(object, bounds) {
  return [object.footprint_m[0] / bounds.size[0], object.visual_height_m / bounds.size[1],
    object.footprint_m[1] / bounds.size[2]];
}

export function sceneAssetIds(scene) {
  return [...new Set(scene.objects.map((object) => object.asset_id === 'user_barrier'
    ? 'safety_barrier' : object.asset_id))];
}

export async function loadSceneMeshes(scene, fetcher = fetch) {
  const entries = await Promise.all(sceneAssetIds(scene).map(async (id) => {
    const response = await fetcher(`/scene-assets/${id}.glb`);
    if (!response.ok) throw new Error(`GLB ${id}: HTTP ${response.status}`);
    return [id, convertBundledMesh(decodeGlb(await response.arrayBuffer()))];
  }));
  return Object.fromEntries(entries);
}

function plane(vertices, normal = [0, 1, 0]) {
  const result = [];
  for (const point of vertices) result.push(...point, ...normal);
  return new Float32Array(result);
}

// Visual-only stock on the authored rack footprint. It never enters SceneModel collision or economics.
function box() {
  const p = [[-.5, 0, -.5], [.5, 0, -.5], [.5, 1, -.5], [-.5, 1, -.5],
    [-.5, 0, .5], [.5, 0, .5], [.5, 1, .5], [-.5, 1, .5]];
  const faces = [[0, 1, 2, 3, [0, 0, -1]], [5, 4, 7, 6, [0, 0, 1]],
    [4, 0, 3, 7, [-1, 0, 0]], [1, 5, 6, 2, [1, 0, 0]],
    [3, 2, 6, 7, [0, 1, 0]], [4, 5, 1, 0, [0, -1, 0]]];
  return new Float32Array(faces.flatMap(([a, b, c, d, normal]) =>
    [p[a], p[b], p[c], p[a], p[c], p[d]].flatMap((point) => [...point, ...normal])));
}

const COLOR = { CHARGE: [.08, .72, .46], PICKUP: [.98, .63, .10],
  DROPOFF: [.90, .21, .26], SHARED_LANE: [.48, .31, .75] };

export class SceneRenderer3D {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext('webgl', { antialias: true, alpha: false, preserveDrawingBuffer: true });
    if (!gl) throw new Error('WebGL недоступен');
    this.gl = gl;
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    this.program = program;
    gl.useProgram(program);
    this.loc = Object.fromEntries(['aPosition', 'aNormal', 'uModel', 'uViewProjection', 'uColor',
      'uCamera', 'uMetallic', 'uRoughness', 'uEmission', 'uAlpha', 'uFloor'].map((name) =>
      [name, name.startsWith('a') ? gl.getAttribLocation(program, name) : gl.getUniformLocation(program, name)]));
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.disable(gl.CULL_FACE);
    this.buffers = [];
  }

  upload(vertices) {
    const buffer = this.gl.createBuffer();
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, buffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, vertices, this.gl.STATIC_DRAW);
    this.buffers.push(buffer);
    return { buffer, count: vertices.length / 6 };
  }

  setMeshes(meshes) {
    const gl = this.gl;
    this.buffers.forEach((buffer) => gl.deleteBuffer(buffer));
    this.buffers = [];
    this.meshes = Object.fromEntries(Object.entries(meshes).map(([id, mesh]) => [id, {
      bounds: mesh.bounds, groups: mesh.groups.map((group) => ({ ...group, ...this.upload(group.vertices) })),
    }]));
  }

  draw(mesh, model, color, metallic = 0, roughness = .85, emission = 0, alpha = 1, floor = 0, mode = this.gl.TRIANGLES) {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, mesh.buffer);
    gl.enableVertexAttribArray(this.loc.aPosition);
    gl.vertexAttribPointer(this.loc.aPosition, 3, gl.FLOAT, false, 24, 0);
    gl.enableVertexAttribArray(this.loc.aNormal);
    gl.vertexAttribPointer(this.loc.aNormal, 3, gl.FLOAT, false, 24, 12);
    gl.uniformMatrix4fv(this.loc.uModel, false, model);
    gl.uniform3fv(this.loc.uColor, color);
    gl.uniform1f(this.loc.uMetallic, metallic);
    gl.uniform1f(this.loc.uRoughness, roughness);
    gl.uniform1f(this.loc.uEmission, emission);
    gl.uniform1f(this.loc.uAlpha, alpha);
    gl.uniform1f(this.loc.uFloor, floor);
    gl.drawArrays(mode, 0, mesh.count);
  }

  render(scene, preset = 'isometric') {
    const gl = this.gl;
    const width = Math.max(1, Math.round(this.canvas.clientWidth * Math.min(devicePixelRatio || 1, 1.5)));
    const height = Math.max(1, Math.round(this.canvas.clientHeight * Math.min(devicePixelRatio || 1, 1.5)));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width; this.canvas.height = height;
    }
    gl.viewport(0, 0, width, height);
    gl.clearColor(.055, .095, .135, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const { width_m: w, length_m: l } = scene.bounds;
    const center = worldToGltf([w / 2, l / 2, 0]);
    const span = Math.max(w, l);
    const camera = preset === 'top' ? [center[0], span * 1.05, center[2] + .01]
      : preset === 'overview' ? [center[0] + span * .39, span * .51, center[2] + span * .81]
        : [center[0] + span * .60, span * .60, center[2] + span * .67];
    const projection = mat4Perspective(Math.PI / 3.1, width / height, .1, span * 5);
    gl.uniformMatrix4fv(this.loc.uViewProjection, false, mat4Multiply(projection, mat4LookAt(camera, center)));
    gl.uniform3fv(this.loc.uCamera, camera);
    const identity = mat4Model([0, 0, 0], [1, 1, 1]);
    const floor = this.upload(plane([[0, -.025, 0], [w, -.025, 0], [w, -.025, -l],
      [0, -.025, 0], [w, -.025, -l], [0, -.025, -l]]));
    this.draw(floor, identity, scene.scene_id === 'clinic' ? [.34, .48, .52]
      : scene.scene_id === 'airport' ? [.21, .32, .38] : [.23, .32, .36], 0, .98, 0, 1, 1);
    gl.deleteBuffer(floor.buffer);
    this.buffers.pop();
    for (const zone of scene.zones) {
      const polygon = zone.polygon_xy_m;
      if (polygon.length < 3) continue;
      const triangles = [];
      for (let i = 1; i < polygon.length - 1; i += 1) {
        triangles.push(worldToGltf([...polygon[0], .015]), worldToGltf([...polygon[i], .015]),
          worldToGltf([...polygon[i + 1], .015]));
      }
      const mesh = this.upload(plane(triangles));
      gl.depthMask(false);
      this.draw(mesh, identity, COLOR[zone.kind] || [.3, .5, .5], 0, .9, .12, .50);
      gl.depthMask(true);
      gl.deleteBuffer(mesh.buffer);
      this.buffers.pop();
    }
    for (const object of scene.objects) {
      const asset = this.meshes?.[object.asset_id === 'user_barrier' ? 'safety_barrier' : object.asset_id];
      if (!asset) continue;
      const scale = objectMeshScale(object, asset.bounds);
      const position = worldToGltf(object.position_m);
      const model = mat4Model(position, scale, object.rotation_yaw_rad || 0);
      for (const group of asset.groups) this.draw(group, model, group.color,
        group.metallic, group.roughness, group.emission);
    }
    const stock = this.upload(box());
    for (const object of scene.objects) {
      if (object.asset_id !== 'pallet_rack') continue;
      const [x, y] = object.position_m;
      const [width, depth] = object.footprint_m;
      const height = object.visual_height_m;
      for (const tier of [.12, .43, .74]) {
        const slab = mat4Model(worldToGltf([x, y, height * tier]),
          [width * .86, Math.max(.09, height * .055), depth * .86], object.rotation_yaw_rad || 0);
        this.draw(stock, slab, [.42, .50, .57], .35, .55);
        const crate = mat4Model(worldToGltf([x, y, height * (tier + .055)]),
          [width * .68, height * .16, depth * .7], object.rotation_yaw_rad || 0);
        this.draw(stock, crate, [.48, .29, .12], 0, .9);
      }
    }
    gl.deleteBuffer(stock.buffer);
    this.buffers.pop();
    for (const route of scene.routes) {
      const segments = [];
      for (let i = 1; i < route.points_xy_m.length; i += 1) {
        segments.push(worldToGltf([...route.points_xy_m[i - 1], .08]),
          worldToGltf([...route.points_xy_m[i], .08]));
      }
      const mesh = this.upload(plane(segments));
      this.draw(mesh, identity, [.06, .38, .79], 0, .8, .22, 1, 0, gl.LINES);
      gl.deleteBuffer(mesh.buffer);
      this.buffers.pop();
    }
  }

  dispose() {
    this.buffers.forEach((buffer) => this.gl.deleteBuffer(buffer));
    this.gl.deleteProgram(this.program);
  }
}
