import test from 'node:test';
import assert from 'node:assert/strict';
import { brainRequest } from '../src/brainRequest.js';

test('client wait is bounded and external cancellation is preserved', async () => {
  const original = global.fetch;
  global.fetch = (_url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(signal.reason), { once: true });
  });
  try {
    await assert.rejects(brainRequest('/mock', {}, 5), /Проверяем сохранённый статус/);
    const controller = new AbortController();
    const pending = brainRequest('/mock', { signal: controller.signal });
    controller.abort();
    await assert.rejects(pending, { name: 'AbortError' });
  } finally { global.fetch = original; }
});

test('HTTP errors and malformed JSON finish with visible errors', async () => {
  const original = global.fetch;
  try {
    for (const status of [401, 429]) {
      global.fetch = async () => new Response('{"detail":"Повторите позже"}', { status });
      await assert.rejects(brainRequest('/mock'), /Повторите позже/);
    }
    global.fetch = async () => new Response('invalid json');
    await assert.rejects(brainRequest('/mock'), SyntaxError);
  } finally { global.fetch = original; }
});
