import test from 'node:test';
import assert from 'node:assert/strict';
import { advancePlaybackTime, playbackPose } from '../src/simulationPlayback.js';

const samples = [
  { t_s: 0, x_m: 0, y_m: 0 },
  { t_s: 80, x_m: 80, y_m: 0 },
];

test('display rates share server timestamps and do not change the path', () => {
  for (const rate of [1, 2, 4, 8]) {
    const cursor = advancePlaybackTime(0, 8, rate, 80);
    assert.equal(cursor, 8 * rate);
    assert.equal(playbackPose(samples, cursor)[0], 8 * rate);
  }
  assert.equal(samples[1].t_s, 80);
});

test('paused clock stays fixed and replay starts from zero at the selected rate', () => {
  const paused = 21;
  assert.equal(advancePlaybackTime(paused, 0, 8, 80), paused);
  assert.equal(advancePlaybackTime(paused, 2, 4, 80), 29);
  assert.equal(advancePlaybackTime(0, 2, 4, 80), 8);
  assert.equal(advancePlaybackTime(78, 2, 8, 80), 80);
});
