import test from 'node:test';
import assert from 'node:assert/strict';
import { playbackDuration, playbackPose } from '../src/simulationPlayback.js';

test('server poses drive the same continuous position for both scene views', () => {
  const poses = [{ t_s: 0, x_m: 2, y_m: 3 }, { t_s: 2, x_m: 6, y_m: 3 },
    { t_s: 4, x_m: 6, y_m: 7 }];
  assert.equal(playbackDuration(poses), 4);
  assert.deepEqual(playbackPose(poses, 0), [2, 3, 0]);
  assert.deepEqual(playbackPose(poses, 1), [4, 3, 0]);
  assert.deepEqual(playbackPose(poses, 3), [6, 5, Math.PI / 2]);
  assert.deepEqual(playbackPose(poses, 5), [6, 7, Math.PI / 2]);
});
