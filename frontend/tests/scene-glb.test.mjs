import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { decodeGlb } from '../../robcraft/src/core/glb-model.js';
import { convertBundledMesh, HD_VARIANTS, objectMeshScale, sceneAssetIds } from '../src/sceneRenderer3D.js';
import { sceneForKind, worldToGltf } from '../src/sceneModel.js';

test('21 bundled GLB meshes decode with colors, normals and metre bounds', async () => {
  const root = new URL('../public/scene-assets/', import.meta.url);
  const manifest = JSON.parse(await readFile(new URL('manifest.json', root), 'utf8'));
  assert.equal(manifest.assets.length, 21);
  const used = new Set(['warehouse', 'airport', 'clinic'].flatMap((kind) => sceneAssetIds(sceneForKind(kind))));
  assert.deepEqual(used, new Set(manifest.assets.map((asset) => asset.asset_id)));
  for (const asset of manifest.assets) {
    const bytes = await readFile(new URL(asset.file, root));
    const groups = decodeGlb(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    const mesh = convertBundledMesh(groups);
    assert(mesh.groups.length > 0, asset.asset_id);
    assert(mesh.groups.every((group) => group.vertices.length >= 18
      && group.vertices.length % 18 === 0
      && group.vertices.every(Number.isFinite)
      && group.color.every((value) => value >= 0 && value <= 1)), asset.asset_id);
    assert(mesh.bounds.size.every((value) => value > 0), asset.asset_id);
  }
});

test('thirteen original Blender assets decode, retain detail and match their provenance manifest', async () => {
  const root = new URL('../public/scene-assets/', import.meta.url);
  const manifest = JSON.parse(await readFile(new URL('recovery-manifest.json', root), 'utf8'));
  assert.equal(manifest.assets.length, 13);
  assert.equal(Object.keys(HD_VARIANTS).length, 10);
  for (const id of [...Object.values(HD_VARIANTS), 'hero_warehouse_shell', 'hero_airport_shell', 'hero_clinic_shell']) {
    const bytes = await readFile(new URL(`${id}.glb`, root));
    const record = manifest.assets.find((asset) => asset.asset_id === id);
    assert.equal(record?.bytes, bytes.length);
    assert.equal(record.sha256, createHash('sha256').update(bytes).digest('hex'));
    const groups = decodeGlb(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    const mesh = convertBundledMesh(groups);
    assert(mesh.groups.length >= 4, `${id}: material variety`);
    assert(mesh.groups.every((group) => typeof group.materialName === 'string' && group.materialName.length > 0),
      `${id}: Blender material names are needed for live surface shading`);
    assert(mesh.groups.reduce((count, group) => count + group.vertices.length / 18, 0) > 100, `${id}: triangle detail`);
    assert(mesh.bounds.size.every((size) => size > 0), `${id}: metric bounds`);
  }
});

test('3D mesh axes use the same one-time world-to-glTF conversion as scene coordinates', () => {
  const triangle = [{ vertices: new Float32Array([
    1, 2, 3, 0, 0, 1, 2, 2, 3, 0, 0, 1, 1, 3, 3, 0, 0, 1,
  ]), color: [1, 0, 0], metallic: 0, roughness: 1, emission: 0 }];
  const mesh = convertBundledMesh(triangle);
  assert.deepEqual([...mesh.groups[0].vertices.slice(0, 3)], worldToGltf([1, 2, 3]));
  assert.deepEqual([...mesh.groups[0].vertices.slice(3, 6)], worldToGltf([0, 0, 1]));
  const rack = sceneForKind('warehouse').objects.find((object) => object.asset_id === 'pallet_rack');
  const scale = objectMeshScale(rack, { size: [4, 3.2, 1.2] });
  assert.deepEqual(scale.map((value, axis) => value * [4, 3.2, 1.2][axis]),
    [rack.footprint_m[0], rack.visual_height_m, rack.footprint_m[1]]);
});
