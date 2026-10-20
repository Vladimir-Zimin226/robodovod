// Small glTF 2.0 GLB adapter for Blender's static class silhouettes.
// It accepts only uncompressed triangle meshes with POSITION and NORMAL.
const COMPONENT_BYTES = { 5121: 1, 5123: 2, 5125: 4, 5126: 4 };

function accessor(json, binary, index) {
  const access = json.accessors[index];
  const view = json.bufferViews[access.bufferView];
  const size = access.type === 'VEC4' ? 4 : access.type === 'VEC3' ? 3 : access.type === 'VEC2' ? 2 : 1;
  const width = COMPONENT_BYTES[access.componentType];
  if (!width || view.buffer !== 0 || access.sparse) throw new Error('Unsupported glTF accessor');
  const stride = view.byteStride || width * size;
  const data = new DataView(binary.buffer, binary.byteOffset, binary.byteLength);
  const offset = (view.byteOffset || 0) + (access.byteOffset || 0);
  const read = (at) => access.componentType === 5126 ? data.getFloat32(at, true)
    : access.componentType === 5125 ? data.getUint32(at, true)
      : access.componentType === 5123 ? data.getUint16(at, true) : data.getUint8(at);
  return Array.from({ length: access.count }, (_, i) => Array.from({ length: size }, (_, j) => read(offset + i * stride + j * width)));
}

function rotate(vector, quaternion) {
  const [x, y, z, w] = quaternion;
  const cross = [y * vector[2] - z * vector[1], z * vector[0] - x * vector[2], x * vector[1] - y * vector[0]];
  const doubled = cross.map(value => value * 2);
  const second = [y * doubled[2] - z * doubled[1], z * doubled[0] - x * doubled[2], x * doubled[1] - y * doubled[0]];
  return vector.map((value, i) => value + w * doubled[i] + second[i]);
}

function faceNormal(a, b, c) {
  const u = b.map((value, i) => value - a[i]);
  const v = c.map((value, i) => value - a[i]);
  const normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
  const length = Math.hypot(...normal) || 1;
  return normal.map(value => value / length);
}

export function decodeGlb(buffer) {
  const header = new DataView(buffer);
  if (header.getUint32(0, true) !== 0x46546c67 || header.getUint32(4, true) !== 2 || header.getUint32(8, true) !== buffer.byteLength)
    throw new Error('Invalid GLB 2.0');
  let offset = 12;
  const chunks = {};
  while (offset < buffer.byteLength) {
    const length = header.getUint32(offset, true);
    const type = header.getUint32(offset + 4, true);
    chunks[type] = new Uint8Array(buffer, offset + 8, length);
    offset += length + 8;
  }
  if (!chunks[0x4e4f534a] || !chunks[0x004e4942]) throw new Error('GLB chunks are missing');
  const json = JSON.parse(new TextDecoder().decode(chunks[0x4e4f534a]));
  if (json.extensionsRequired?.length) throw new Error('Compressed GLB is unsupported');
  const binary = chunks[0x004e4942];
  const byMaterial = new Map();
  const groupMaterials = new Map();
  for (const node of json.nodes || []) {
    if (node.mesh === undefined) continue;
    if (node.children?.length || node.matrix) throw new Error('Nested GLB nodes are unsupported');
    const translation = node.translation || [0, 0, 0];
    const rotation = node.rotation || [0, 0, 0, 1];
    const scale = node.scale || [1, 1, 1];
    for (const primitive of json.meshes[node.mesh].primitives) {
      if (primitive.mode !== undefined && primitive.mode !== 4) throw new Error('Only triangles are supported');
      const positions = accessor(json, binary, primitive.attributes.POSITION);
      const normals = primitive.attributes.NORMAL === undefined ? null
        : accessor(json, binary, primitive.attributes.NORMAL);
      const colorAccessor = primitive.attributes.COLOR_0 === undefined ? null
        : json.accessors[primitive.attributes.COLOR_0];
      const colors = colorAccessor ? accessor(json, binary, primitive.attributes.COLOR_0) : null;
      const indices = primitive.indices === undefined ? positions.map((_, i) => [i]).flat() : accessor(json, binary, primitive.indices).flat();
      const material = json.materials?.[primitive.material] || {};
      const vertexColor = colors?.[0]?.slice(0, 3).map(value => colorAccessor.normalized
        ? value / (colorAccessor.componentType === 5121 ? 255 : 65535) : value);
      const color = vertexColor || material.pbrMetallicRoughness?.baseColorFactor?.slice(0, 3) || [.5, .5, .5];
      const key = `${primitive.material ?? -1}:${color.join(',')}`;
      const vertices = byMaterial.get(key) || [];
      for (let triangle = 0; triangle < indices.length; triangle += 3) {
        const corners = indices.slice(triangle, triangle + 3).map(index =>
          rotate(positions[index].map((value, i) => value * scale[i]), rotation)
            .map((value, i) => value + translation[i]));
        const flatNormal = faceNormal(...corners);
        corners.forEach((position, corner) => {
          const normal = normals ? rotate(normals[indices[triangle + corner]], rotation) : flatNormal;
          vertices.push(...position, ...normal);
        });
      }
      byMaterial.set(key, vertices);
      groupMaterials.set(key, { color, materialName: material.name || '',
        emission: material.emissiveFactor?.some(Boolean) ? .4 : 0,
        metallic: material.pbrMetallicRoughness?.metallicFactor || 0,
        roughness: material.pbrMetallicRoughness?.roughnessFactor ?? 1 });
    }
  }
  return [...byMaterial].map(([key, vertices]) => {
    const material = groupMaterials.get(key);
    return { vertices: new Float32Array(vertices), ...material };
  });
}

export const ROBOT_ASSET_NAMES = Object.freeze(['pallet-amr', 'forklift', 'cleaning-robot', 'medical-cart']);
export const ENVIRONMENT_ASSET_NAMES = Object.freeze(['rack-module', 'pallet-load', 'charger-station']);
export const SCENE_ASSET_NAMES = Object.freeze(['pallet_rack', 'pallet_stack', 'pallet_amr', 'forklift_robot', 'charging_dock', 'worker', 'conveyor', 'baggage_cart', 'airport_tug', 'safety_barrier', 'aircraft_marker', 'hospital_bed', 'hospital_cart', 'nurse_desk', 'indoor_delivery_robot', 'clinic_wall_module', 'warehouse_column', 'door_frame', 'painted_floor_marker', 'traffic_cone', 'clinic_door']);

async function loadModels(names, directory, fetcher) {
  const entries = await Promise.all(names.map(async name => {
    const url = new URL(`../../public/assets/${directory}/${name}.glb`, import.meta.url);
    const response = await fetcher(url);
    if (!response.ok) throw new Error(`GLB ${name}: HTTP ${response.status}`);
    return [name, decodeGlb(await response.arrayBuffer())];
  }));
  return Object.fromEntries(entries);
}

export function loadRobotModels(fetcher = fetch) { return loadModels(ROBOT_ASSET_NAMES, 'robots', fetcher); }
export function loadEnvironmentModels(fetcher = fetch) { return loadModels(ENVIRONMENT_ASSET_NAMES, 'environment', fetcher); }
export async function loadSceneAssets(fetcher = fetch) {
  const entries = await Promise.all(SCENE_ASSET_NAMES.map(async name => {
    const response = await fetcher(`/scene-assets/${name}.glb`);
    if (!response.ok) throw new Error(`GLB ${name}: HTTP ${response.status}`);
    return [name, decodeGlb(await response.arrayBuffer())];
  }));
  return Object.fromEntries(entries);
}
