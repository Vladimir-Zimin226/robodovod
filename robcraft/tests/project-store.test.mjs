import test from 'node:test';
import assert from 'node:assert/strict';
import { RobCraftProjectStore, SceneSaveConflict } from '../src/editor/project-store.js';

const projectId = '01234567-89ab-4cde-8fab-0123456789ab';
const response = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test('сцена проекта загружается и сохраняется с CSRF и ожидаемой ревизией', async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    if (!options || !options.method) return response(200, { revision: 2, name: 'Склад', document: { scene: 1 }, versions: [] });
    return response(200, { revision: 3, name: 'Склад', saved_at: '2026-10-20T00:00:00Z' });
  };
  const store = new RobCraftProjectStore(projectId, fetcher, () => 'csrf-secret');
  assert.deepEqual(await store.load(), { scene: 1 });
  assert.equal(store.revision, 2);
  await store.save({ scene: 2 }, 'Склад');
  assert.equal(store.revision, 3);
  assert.equal(calls[1].url, `/api/projects/${projectId}/robcraft-scene`);
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'csrf-secret');
  assert.deepEqual(JSON.parse(calls[1].options.body), { expected_revision: 2, name: 'Склад', document: { scene: 2 } });
});

test('конфликт не меняет локальную ревизию и не выдаёт ложное сохранение', async () => {
  const store = new RobCraftProjectStore(projectId, async () => response(409, { detail: { current_revision: 7 } }));
  store.revision = 6;
  await assert.rejects(store.save({}, 'Склад'), (error) => error instanceof SceneSaveConflict && error.currentRevision === 7);
  assert.equal(store.revision, 6);
});

test('Сохранить как создаёт проект из текущего документа и сохраняет исходную ревизию', async () => {
  const calls = [];
  const newId = '11234567-89ab-4cde-8fab-0123456789ab';
  const store = new RobCraftProjectStore(projectId, async (url, options) => {
    calls.push({ url, options });
    return response(201, { project_id: newId, revision: 1, name: 'Копия', saved_at: '2026-10-20T00:00:00Z' });
  }, () => 'csrf-secret');
  store.revision = 4;
  const result = await store.saveAs({ scene: 5 }, 'Копия');
  assert.equal(result.project_id, newId);
  assert.equal(store.revision, 4);
  assert.equal(calls[0].url, `/api/projects/${projectId}/robcraft-scene/save-as`);
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(calls[0].options.headers['X-CSRF-Token'], 'csrf-secret');
  assert.deepEqual(JSON.parse(calls[0].options.body), { expected_revision: 4, name: 'Копия', document: { scene: 5 } });
});

test('Сохранить как сообщает о конфликте без смены проекта', async () => {
  const store = new RobCraftProjectStore(projectId, async () => response(409, { detail: { current_revision: 5 } }));
  store.revision = 4;
  await assert.rejects(store.saveAs({}, 'Копия'), (error) => error instanceof SceneSaveConflict && error.currentRevision === 5);
  assert.equal(store.revision, 4);
});
