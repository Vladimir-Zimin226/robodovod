import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { EvidenceExportSession } from '../../src/evidenceExportApi.js';

const responses = JSON.parse(await readFile(process.argv[2], 'utf8'));
const { manifest, projectId, runId } = responses;
const saves = [];
let override = {};
let delayed;
const session = new EvidenceExportSession({
  fetchImpl: async (url) => {
    if (url.includes('/manifest')) return { ok: true, json: async () => ({ ...manifest, ...override.manifest }) };
    const path = new URL(url, 'http://localhost').pathname.split('/').at(-1);
    const response = responses[path];
    assert.ok(response, path);
    return { ok: true, headers: new Headers({ ...response.headers, ...override.headers }), blob: async () => {
      if (override.delay) await new Promise((resolve) => { delayed = resolve; });
      return new Blob([Buffer.from(override.bytes || response.bytes, 'base64')]);
    } };
  },
  saveImpl: (blob) => saves.push(blob),
});
await session.downloadInvestorReport(projectId, runId, manifest.simulation_request_id);
assert.equal(saves.length, 1);
assert.equal(Buffer.from(await saves[0].arrayBuffer()).toString('base64'), responses['investor-report-preview.pdf'].bytes);
for (const failure of [
  { headers: { 'X-Report-Presentation': 'unknown' } },
  { headers: { 'X-Report-Source-Digest': 'sha256:' + '0'.repeat(64) } },
  { headers: { 'X-Simulation-Report-Digest': 'sha256:' + '0'.repeat(64) } },
  { manifest: { run_id: 'other-run' } },
  { bytes: Buffer.from('corrupt').toString('base64') },
]) {
  override = failure;
  await assert.rejects(session.downloadInvestorReport(projectId, runId, manifest.simulation_request_id));
  assert.equal(saves.length, 1);
}
override = { delay: true };
const pending = session.downloadInvestorReport(projectId, runId, manifest.simulation_request_id);
while (!delayed) await new Promise((resolve) => setTimeout(resolve, 1));
session.cancel(); delayed();
await assert.rejects(pending, /stale/);
assert.equal(saves.length, 1);
override = {};
await session.download(projectId, runId, manifest.simulation_request_id);
for (const format of ['xlsx', 'csv', ...(manifest.visualization_filename ? ['svg'] : [])]) {
  await session.downloadFormat(projectId, runId, format, manifest.simulation_request_id);
}
if (!manifest.visualization_filename) await assert.rejects(session.downloadFormat(projectId, runId, 'svg'), /unavailable/);
console.log(JSON.stringify({ presentation: responses['investor-report.pdf'].headers['x-report-presentation'], saves: saves.length }));
