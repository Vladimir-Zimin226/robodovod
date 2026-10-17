// Small glTF 2.0 GLB adapter for Blender's static class silhouettes.
// It accepts only uncompressed triangle meshes with POSITION and NORMAL.
const COMPONENT_BYTES = { 5121: 1, 5123: 2, 5125: 4, 5126: 4 };

function accessor(json, binary, index) {
  const access = json.accessors[index];
  const view = json.bufferViews[access.bufferView];
  const size = access.type === 'VEC3' ? 3 : access.type === 'VEC2' ? 2 : 1;
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
  for (const node of json.nodes || []) {
    if (node.mesh === undefined) continue;
    if (node.children?.length || node.matrix) throw new Error('Nested GLB nodes are unsupported');
    const translation = node.translation || [0, 0, 0];
    const rotation = node.rotation || [0, 0, 0, 1];
    const scale = node.scale || [1, 1, 1];
    for (const primitive of json.meshes[node.mesh].primitives) {
      if (primitive.mode !== undefined && primitive.mode !== 4) throw new Error('Only triangles are supported');
      const positions = accessor(json, binary, primitive.attributes.POSITION);
      const normals = accessor(json, binary, primitive.attributes.NORMAL);
      const indices = primitive.indices === undefined ? positions.map((_, i) => [i]).flat() : accessor(json, binary, primitive.indices).flat();
      const key = primitive.material ?? -1;
      const vertices = byMaterial.get(key) || [];
      for (const index of indices) {
        const position = rotate(positions[index].map((value, i) => value * scale[i]), rotation);
        const normal = rotate(normals[index], rotation);
        vertices.push(...position.map((value, i) => value + translation[i]), ...normal);
      }
      byMaterial.set(key, vertices);
    }
  }
  return [...byMaterial].map(([materialIndex, vertices]) => {
    const material = json.materials?.[materialIndex] || {};
    return { vertices: new Float32Array(vertices), color: material.pbrMetallicRoughness?.baseColorFactor?.slice(0, 3) || [.5, .5, .5],
      emission: material.emissiveFactor?.some(Boolean) ? .4 : 0,
      metallic: material.pbrMetallicRoughness?.metallicFactor || 0 };
  });
}

export const ROBOT_ASSET_NAMES = Object.freeze(['pallet-amr', 'forklift', 'cleaning-robot', 'medical-cart']);
export const ENVIRONMENT_ASSET_NAMES = Object.freeze(['rack-module', 'pallet-load', 'charger-station']);

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
