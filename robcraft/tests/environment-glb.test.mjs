import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { decodeGlb, ENVIRONMENT_ASSET_NAMES } from '../src/core/glb-model.js';

const HEIGHTS = { 'rack-module': 2.6, 'pallet-load': .75, 'charger-station': .72 };

for (const name of ENVIRONMENT_ASSET_NAMES) test(`Blender environment ${name} fits visual budget`, async () => {
  const file = await readFile(new URL(`../public/assets/environment/${name}.glb`, import.meta.url));
  const groups = decodeGlb(file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength));
  const triangles = groups.reduce((sum, group) => sum + group.vertices.length / 18, 0);
  assert.ok(groups.length >= 3 && groups.length <= 8);
  assert.ok(triangles > 500 && triangles < 3500, `${name}: ${triangles} triangles`);
  assert.ok(file.length < 160_000, `${name}: ${file.length} bytes`);
  const y = groups.flatMap(group => Array.from({ length: group.vertices.length / 6 }, (_, i) => group.vertices[i * 6 + 1]));
  assert.ok(Math.min(...y) >= -.01);
  assert.ok(Math.abs(Math.max(...y) - HEIGHTS[name]) < .06);
});
