import assert from 'node:assert/strict';
import test from 'node:test';

import { requestDiagnosticBundle } from '../src/diagnosticExportApi.js';

test('diagnostic download uses admin POST, cookies and CSRF', async () => {
  const bytes = new Blob(['diagnostic ZIP']);
  const calls = [];
  const result = await requestDiagnosticBundle(async (url, options) => {
    calls.push({ url, options });
    return { ok: true, blob: async () => bytes };
  }, 'csrf-value', 'https://example.test');
  assert.equal(result, bytes);
  assert.deepEqual(calls, [{
    url: 'https://example.test/api/admin/diagnostics/export',
    options: {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRF-Token': 'csrf-value' },
    },
  }]);
});

test('diagnostic download surfaces safe server error', async () => {
  await assert.rejects(
    requestDiagnosticBundle(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'administrator role required' }),
    }), 'csrf-value'),
    /administrator role required/,
  );
});
