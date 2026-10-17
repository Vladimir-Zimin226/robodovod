import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { decodeGlb, ROBOT_ASSET_NAMES } from '../src/core/glb-model.js';

for (const name of ROBOT_ASSET_NAMES) test(`Blender asset ${name} has bounded triangle geometry`, async () => {
  const file = await readFile(new URL(`../public/assets/robots/${name}.glb`, import.meta.url));
  const array = file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength);
  const groups = decodeGlb(array);
  assert.ok(groups.length >= 3 && groups.length <= 12);
  const triangles = groups.reduce((sum, group) => sum + group.vertices.length / 18, 0);
  assert.ok(triangles > 100 && triangles < 5000, `triangle budget: ${triangles}`);
  const points = groups.flatMap(group => Array.from({ length: group.vertices.length / 6 }, (_, i) =>
    [group.vertices[i * 6], group.vertices[i * 6 + 1], group.vertices[i * 6 + 2]]));
  const limits = [0, 1, 2].map(axis => [Math.min(...points.map(point => point[axis])), Math.max(...points.map(point => point[axis]))]);
  assert.ok(limits[0][1] - limits[0][0] <= 1.5);
  assert.ok(limits[1][0] >= -.01 && limits[1][1] <= 2.1);
  assert.ok(limits[2][1] - limits[2][0] <= 2.7);
  assert.ok(file.length < 250_000, `asset budget: ${file.length}`);
});
