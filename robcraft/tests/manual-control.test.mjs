import test from 'node:test';
import assert from 'node:assert/strict';

import { Player } from '../src/player.js';

function controls() {
  const documentListeners = new Map();
  const canvasListeners = new Map();
  const canvas = {
    addEventListener: (name, listener) => canvasListeners.set(name, listener),
    requestPointerLock() {},
  };
  const document = {
    pointerLockElement: canvas,
    addEventListener: (name, listener) => documentListeners.set(name, listener),
  };
  return { canvas, document, documentListeners };
}

test('manual inspector selects the nearest robot, station or zone in view', () => {
  const previousDocument = globalThis.document;
  const environment = controls();
  globalThis.document = environment.document;
  try {
    const player = new Player(environment.canvas);
    player.position = [0, 1.72, 0];
    player.yaw = 0;
    player.pitch = 0;
    const station = { entityType: 'station', position: [0, 0, -3] };
    const zone = { entityType: 'zone', position: [0, 0, -5] };
    assert.equal(player.lookingAt([zone, station], 6), station);
    assert.equal(player.lookingAt([zone], 4), null);
  } finally {
    globalThis.document = previousDocument;
  }
});

test('manual WASD movement respects scene solids', () => {
  const previousDocument = globalThis.document;
  const environment = controls();
  globalThis.document = environment.document;
  try {
    const player = new Player(environment.canvas);
    player.enabled = true;
    environment.documentListeners.get('keydown')({ code: 'KeyW' });
    player.update(.2, [{ position: [0, 1, -.7], scale: [2, 2, 1] }]);
    assert.deepEqual(player.position, [0, 1.72, 0]);
    environment.documentListeners.get('keyup')({ code: 'KeyW' });
    player.update(.2, []);
    assert.equal(player.moving, false);
  } finally {
    globalThis.document = previousDocument;
  }
});
