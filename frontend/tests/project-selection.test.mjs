import test from 'node:test';
import assert from 'node:assert/strict';
import {
  forgetProjectId, readRememberedProjectId, rememberProjectId, selectRestorableProject,
} from '../src/projectSelection.js';

const projects = [{ id: 'project.one' }, { id: 'project.two' }];

test('a sole owned project is restored after page reload', () => {
  assert.deepEqual(selectRestorableProject(projects.slice(0, 1), null), projects[0]);
});

test('multiple projects require a remembered owned choice or explicit selection', () => {
  assert.equal(selectRestorableProject(projects, null), null);
  assert.deepEqual(selectRestorableProject(projects, 'project.two'), projects[1]);
  assert.equal(selectRestorableProject(projects, 'project.other-user'), null);
});

test('remembered project IDs are scoped per user and cleared on logout', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  rememberProjectId(storage, 'user.one', 'project.one');
  assert.equal(readRememberedProjectId(storage, 'user.one'), 'project.one');
  assert.equal(readRememberedProjectId(storage, 'user.two'), null);
  forgetProjectId(storage, 'user.one');
  assert.equal(readRememberedProjectId(storage, 'user.one'), null);
});
