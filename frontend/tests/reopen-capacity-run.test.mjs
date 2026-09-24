import test from 'node:test';
import assert from 'node:assert/strict';
import { reopenCapacityRun } from '../src/reopenCapacityRun.js';

const run = { id: 'run.one', revision_id: 'draft.5' };
const opened = {
  ...run, run_kind: 'CAPACITY_ANALYSIS', project_id: 'project.one',
  input_snapshot: { project_id: 'project.one', input_revision: 'draft.5' },
};
const capacity = { run_id: 'run.one', input_revision: 'draft.5' };

test('reopening C11 retains the immutable input needed by the economics form', async () => {
  const result = await reopenCapacityRun({
    projectId: 'project.one', run,
    readRun: async () => opened,
    readCapacity: async () => capacity,
  });
  assert.deepEqual(result.input_snapshot, opened.input_snapshot);
  assert.deepEqual(result.result_snapshot, capacity);
});

test('reopening rejects mixed project, run or revision snapshots', async () => {
  for (const variant of [
    { opened: { ...opened, project_id: 'project.other' }, capacity },
    { opened: { ...opened, input_snapshot: null }, capacity },
    { opened, capacity: { ...capacity, run_id: 'run.other' } },
    { opened, capacity: { ...capacity, input_revision: 'draft.4' } },
  ]) {
    await assert.rejects(reopenCapacityRun({
      projectId: 'project.one', run,
      readRun: async () => variant.opened,
      readCapacity: async () => variant.capacity,
    }), /не совпадают/);
  }
});
