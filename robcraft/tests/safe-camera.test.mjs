import test from 'node:test';
import assert from 'node:assert/strict';
import { Player } from '../src/player.js';

test('safe scene keeps walls solid during manual flight', () => {
  const previous = globalThis.document;
  const canvas = { addEventListener() {} };
  globalThis.document = { addEventListener() {}, pointerLockElement: canvas };
  try {
    const player = new Player(canvas);
    player.enabled = true;
    player.flying = true;
    player.position = [0, 5, 0];
    player.keys.add('KeyW');
    const wall = { position: [0, 1.6, -.8], scale: [4, 3.2, .4] };
    player.update(.1, [wall], true);
    assert.equal(player.position[2], 0);
    player.update(.1, [wall], false);
    assert.ok(player.position[2] < 0, 'legacy free flight is unchanged');
  } finally {
    globalThis.document = previous;
  }
});
