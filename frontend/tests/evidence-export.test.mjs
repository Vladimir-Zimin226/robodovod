import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { EvidenceExportSession, parseEvidenceManifest } from '../src/evidenceExportApi.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const manifest = JSON.parse(await readFile(path.join(ROOT, 'contracts/fixtures/calculation-evidence-export-v1.golden.json'), 'utf8'));
const manifestV2 = JSON.parse(await readFile(path.join(ROOT, 'contracts/fixtures/calculation-evidence-export-v2.golden.json'), 'utf8'));

function jsonResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => structuredClone(body) };
}

function zipResponse(digest) {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'X-Export-Manifest-Digest': digest }),
    blob: async () => new Blob(['zip']),
  };
}

test('strict manifest parser binds project/run and rejects version or extra fields', () => {
  assert.equal(parseEvidenceManifest(structuredClone(manifest), {
    projectId: manifest.project_id,
    runId: manifest.run_id,
  }).manifest_digest, manifest.manifest_digest);
  assert.throws(() => parseEvidenceManifest({ ...manifest, schema_version: 'calculation-evidence-export-manifest-v3' }), /unsupported/);
  assert.throws(() => parseEvidenceManifest({ ...manifest, client_total: '1.00' }), /unknown or missing/);
  assert.throws(() => parseEvidenceManifest(structuredClone(manifest), { runId: 'another-run' }), /run binding/);
  assert.equal(parseEvidenceManifest(structuredClone(manifestV2), { runId: manifestV2.run_id }).entrypoint_filename, 'НАЧНИТЕ_ЗДЕСЬ.md');
  assert.throws(() => parseEvidenceManifest({ ...manifestV2, report_filename: 'TechnicalDump.pdf' }), /entrypoint/);
});

test('v2 browser download uses a Windows-friendly Russian filename and manifest binding', async () => {
  const saved = [];
  const session = new EvidenceExportSession({
    fetchImpl: async (url) => url.endsWith('/manifest') ? jsonResponse(manifestV2) : zipResponse(manifestV2.manifest_digest),
    saveImpl: (blob, filename) => saved.push(filename),
  });
  await session.download(manifestV2.project_id, manifestV2.run_id);
  assert.equal(saved[0], `Рободовод, доказательства № ${manifestV2.run_id} от 01.01.2026.zip`);
});

test('download uses same-origin credentials and saves only a digest-bound bundle', async () => {
  const requests = [];
  const saved = [];
  const responses = [jsonResponse(manifest), zipResponse(manifest.manifest_digest)];
  const session = new EvidenceExportSession({
    fetchImpl: async (url, options) => { requests.push({ url, options }); return responses.shift(); },
    saveImpl: (blob, filename) => saved.push({ blob, filename }),
  });
  const result = await session.download(manifest.project_id, manifest.run_id);
  assert.equal(result.manifest_digest, manifest.manifest_digest);
  assert.equal(requests.length, 2);
  assert.ok(requests.every((item) => item.options.credentials === 'include'));
  assert.match(requests[0].url, /^\/api\/projects\//);
  assert.equal(saved[0].filename, `robomera-evidence-${manifest.run_id}.zip`);
});

test('download invokes native-style fetch with the global receiver', async () => {
  const responses = [jsonResponse(manifest), zipResponse(manifest.manifest_digest)];
  const saved = [];
  const browserFetch = function () {
    if (this !== globalThis) throw new TypeError('Illegal invocation');
    return responses.shift();
  };
  const session = new EvidenceExportSession({
    fetchImpl: browserFetch,
    saveImpl: (blob) => saved.push(blob),
  });
  await session.download(manifest.project_id, manifest.run_id);
  assert.equal(saved.length, 1);
});

test('standalone PDF saves only when its source matches the reopened run manifest', async () => {
  const reportResponse = (digest) => ({
    ok: true, status: 200,
    headers: new Headers({ 'X-Report-Source-Digest': digest }),
    blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
  });
  const saved = [];
  const session = new EvidenceExportSession({
    fetchImpl: async (url) => url.endsWith('/manifest')
      ? jsonResponse(manifest)
      : reportResponse(manifest.source_snapshot_digests.result),
    saveImpl: (blob, filename) => saved.push({ blob, filename }),
  });
  await session.downloadReport(manifest.project_id, manifest.run_id);
  const [year, month, day] = manifest.snapshot_captured_at.slice(0, 10).split('-');
  assert.equal(saved[0].filename, `Рободовод, отчёт № ${manifest.run_id} от ${day}.${month}.${year}.pdf`);
  const mismatch = new EvidenceExportSession({
    fetchImpl: async (url) => url.endsWith('/manifest')
      ? jsonResponse(manifest)
      : reportResponse(`sha256:${'0'.repeat(64)}`),
    saveImpl: () => saved.push('unexpected'),
  });
  await assert.rejects(mismatch.downloadReport(manifest.project_id, manifest.run_id), /digest binding mismatch/);
  assert.equal(saved.length, 1);
});

test('digest mismatch, HTTP error and stale response cannot trigger a download', async () => {
  const saved = [];
  let responses = [jsonResponse(manifest), zipResponse(`sha256:${'0'.repeat(64)}`)];
  const mismatch = new EvidenceExportSession({
    fetchImpl: async () => responses.shift(), saveImpl: (...args) => saved.push(args),
  });
  await assert.rejects(mismatch.download(manifest.project_id, manifest.run_id), /digest binding mismatch/);
  assert.equal(saved.length, 0);

  const failed = new EvidenceExportSession({ fetchImpl: async () => jsonResponse({}, 404) });
  await assert.rejects(failed.loadManifest(manifest.project_id, manifest.run_id), /unavailable \(404\)/);

  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const stale = new EvidenceExportSession({ fetchImpl: async () => pending });
  const request = stale.loadManifest(manifest.project_id, manifest.run_id);
  stale.cancel();
  release(jsonResponse(manifest));
  await assert.rejects(request, /stale evidence response/);
});

test('legacy report utilities are offline server adapters without report arithmetic', async () => {
  for (const name of ['generateReport.js', 'generateZonalReport.js']) {
    const source = await readFile(path.join(ROOT, 'frontend/src/utils', name), 'utf8');
    assert.match(source, /downloadEvidenceExport/);
    assert.doesNotMatch(source, /html2canvas|jsPDF|cdnjs|fetch\s*\(\s*['"]https?:/i);
  }
  const app = await readFile(path.join(ROOT, 'frontend/src/App.jsx'), 'utf8');
  assert.match(app, /EvidenceExportPanel/);
  assert.match(app, /HistoricalRunViewer/);
  assert.doesNotMatch(app, /saveAnalysis/);
});
