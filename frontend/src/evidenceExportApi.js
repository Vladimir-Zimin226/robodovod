const API = import.meta.env?.VITE_API_URL || '';
const DIGEST = /^sha256:[0-9a-f]{64}$/;
const ROOT_KEYS = [
  'schema_version', 'run_id', 'project_id', 'run_kind', 'revision_id',
  'snapshot_captured_at', 'export_policy_version', 'generator_version',
  'versions', 'source_snapshot_digests', 'sections', 'artifacts',
  'bundle_content_digest', 'limitations', 'manifest_digest',
];
const SECTION_KEYS = ['name', 'status', 'filename', 'record_count', 'reason_code', 'source_refs'];
const ARTIFACT_KEYS = ['filename', 'media_type', 'byte_size', 'sha256'];

function exactKeys(value, allowed, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label}: invalid object`);
  const actual = Object.keys(value).sort();
  const expected = [...allowed].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error(`${label}: unknown or missing field`);
  }
}

export function parseEvidenceManifest(value, expected = {}) {
  exactKeys(value, ROOT_KEYS, 'evidence manifest');
  if (value.schema_version !== 'calculation-evidence-export-manifest-v1') throw new Error('unsupported evidence manifest version');
  if (expected.projectId && value.project_id !== expected.projectId) throw new Error('evidence project binding mismatch');
  if (expected.runId && value.run_id !== expected.runId) throw new Error('evidence run binding mismatch');
  if (!DIGEST.test(value.manifest_digest) || !DIGEST.test(value.bundle_content_digest)) throw new Error('invalid evidence digest');
  if (!Array.isArray(value.sections) || !Array.isArray(value.artifacts) || !Array.isArray(value.limitations)) throw new Error('invalid evidence collections');
  value.sections.forEach((section) => {
    exactKeys(section, SECTION_KEYS, 'evidence section');
    if (!['AVAILABLE', 'NOT_AVAILABLE'].includes(section.status)) throw new Error('invalid evidence section status');
  });
  value.artifacts.forEach((artifact) => {
    exactKeys(artifact, ARTIFACT_KEYS, 'evidence artifact');
    if (!DIGEST.test(artifact.sha256)) throw new Error('invalid evidence artifact digest');
  });
  return Object.freeze(value);
}

function defaultSave(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function reportFilename(runId, capturedAt) {
  const date = String(capturedAt).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('invalid report date');
  const [year, month, day] = date.split('-');
  return `Рободовод, отчёт № ${runId} от ${day}.${month}.${year}.pdf`;
}

export class EvidenceExportSession {
  constructor({ fetchImpl = globalThis.fetch, saveImpl = defaultSave } = {}) {
    // Window.fetch requires Window as its receiver in browsers.
    this.fetchImpl = (...args) => Reflect.apply(fetchImpl, globalThis, args);
    this.saveImpl = saveImpl;
    this.sequence = 0;
  }

  cancel() {
    this.sequence += 1;
  }

  async loadManifest(projectId, runId) {
    const sequence = ++this.sequence;
    const response = await this.fetchImpl(
      `${API}/api/projects/${encodeURIComponent(projectId)}/analysis-runs/${encodeURIComponent(runId)}/exports/manifest`,
      { credentials: 'include' },
    );
    if (!response.ok) throw new Error(`export manifest unavailable (${response.status})`);
    const manifest = parseEvidenceManifest(await response.json(), { projectId, runId });
    if (sequence !== this.sequence) throw new Error('stale evidence response');
    return manifest;
  }

  async download(projectId, runId) {
    const sequence = ++this.sequence;
    const base = `${API}/api/projects/${encodeURIComponent(projectId)}/analysis-runs/${encodeURIComponent(runId)}/exports`;
    const manifestResponse = await this.fetchImpl(`${base}/manifest`, { credentials: 'include' });
    if (!manifestResponse.ok) throw new Error(`export manifest unavailable (${manifestResponse.status})`);
    const manifest = parseEvidenceManifest(await manifestResponse.json(), { projectId, runId });
    if (sequence !== this.sequence) throw new Error('stale evidence response');
    const bundleResponse = await this.fetchImpl(`${base}/evidence.zip`, { credentials: 'include' });
    if (!bundleResponse.ok) throw new Error(`evidence bundle unavailable (${bundleResponse.status})`);
    if (bundleResponse.headers.get('X-Export-Manifest-Digest') !== manifest.manifest_digest) {
      throw new Error('evidence bundle digest binding mismatch');
    }
    if (sequence !== this.sequence) throw new Error('stale evidence response');
    const blob = await bundleResponse.blob();
    if (sequence !== this.sequence) throw new Error('stale evidence response');
    const filename = `robomera-evidence-${runId}.zip`;
    this.saveImpl(blob, filename);
    return manifest;
  }

  async downloadReport(projectId, runId) {
    const sequence = ++this.sequence;
    const base = `${API}/api/projects/${encodeURIComponent(projectId)}/analysis-runs/${encodeURIComponent(runId)}/exports`;
    const manifestResponse = await this.fetchImpl(`${base}/manifest`, { credentials: 'include' });
    if (!manifestResponse.ok) throw new Error(`export manifest unavailable (${manifestResponse.status})`);
    const manifest = parseEvidenceManifest(await manifestResponse.json(), { projectId, runId });
    if (sequence !== this.sequence) throw new Error('stale evidence response');
    const reportResponse = await this.fetchImpl(`${base}/report.pdf`, { credentials: 'include' });
    if (!reportResponse.ok) throw new Error(`calculation report unavailable (${reportResponse.status})`);
    if (reportResponse.headers.get('X-Report-Source-Digest') !== manifest.source_snapshot_digests.result) {
      throw new Error('calculation report source digest binding mismatch');
    }
    const blob = await reportResponse.blob();
    if (sequence !== this.sequence) throw new Error('stale evidence response');
    this.saveImpl(blob, reportFilename(runId, manifest.snapshot_captured_at));
    return manifest;
  }
}

export async function downloadEvidenceExport({ projectId, runId, session = new EvidenceExportSession() }) {
  return session.download(projectId, runId);
}
