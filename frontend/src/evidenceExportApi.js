const API = import.meta.env?.VITE_API_URL || '';
const DIGEST = /^sha256:[0-9a-f]{64}$/;
const ROOT_KEYS = [
  'schema_version', 'run_id', 'project_id', 'run_kind', 'revision_id',
  'snapshot_captured_at', 'export_policy_version', 'generator_version',
  'versions', 'source_snapshot_digests', 'sections', 'artifacts',
  'bundle_content_digest', 'limitations', 'manifest_digest',
];
const ROOT_KEYS_V2 = [...ROOT_KEYS, 'entrypoint_filename', 'report_filename', 'linked_capacity_run_id', 'linked_capacity_snapshot_digests'];
const ROOT_KEYS_V3 = [...ROOT_KEYS_V2, 'presentation_version'];
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
  if (!['calculation-evidence-export-manifest-v1', 'calculation-evidence-export-manifest-v2', 'calculation-evidence-export-manifest-v3'].includes(value?.schema_version)) throw new Error('unsupported evidence manifest version');
  const isV3 = value.schema_version === 'calculation-evidence-export-manifest-v3';
  const isV2 = value.schema_version === 'calculation-evidence-export-manifest-v2' || isV3;
  exactKeys(value, isV3 ? ROOT_KEYS_V3 : isV2 ? ROOT_KEYS_V2 : ROOT_KEYS, 'evidence manifest');
  if (isV3 && (value.presentation_version !== 'readable-presentation-v2'
    || value.export_policy_version !== 'calculation-evidence-export-policy-v3'
    || value.generator_version !== 'snapshot-evidence-export-v3')) throw new Error('unsupported readable presentation version');
  if (expected.projectId && value.project_id !== expected.projectId) throw new Error('evidence project binding mismatch');
  if (expected.runId && value.run_id !== expected.runId) throw new Error('evidence run binding mismatch');
  if (!DIGEST.test(value.manifest_digest) || !DIGEST.test(value.bundle_content_digest)) throw new Error('invalid evidence digest');
  if (!value.source_snapshot_digests || !DIGEST.test(value.source_snapshot_digests.result)
    || Object.values(value.source_snapshot_digests).some((digest) => digest != null && !DIGEST.test(digest))) {
    throw new Error('invalid evidence source snapshot digest');
  }
  if (!Array.isArray(value.sections) || !Array.isArray(value.artifacts) || !Array.isArray(value.limitations)) throw new Error('invalid evidence collections');
  value.sections.forEach((section) => {
    exactKeys(section, SECTION_KEYS, 'evidence section');
    if (!['AVAILABLE', 'NOT_AVAILABLE'].includes(section.status)) throw new Error('invalid evidence section status');
  });
  value.artifacts.forEach((artifact) => {
    exactKeys(artifact, ARTIFACT_KEYS, 'evidence artifact');
    if (!DIGEST.test(artifact.sha256)) throw new Error('invalid evidence artifact digest');
  });
  if (isV2) {
    if (value.entrypoint_filename !== 'НАЧНИТЕ_ЗДЕСЬ.md' || value.report_filename !== 'Отчёт_Рободовод.pdf') throw new Error('invalid evidence package entrypoint');
    if (!value.artifacts.some((artifact) => artifact.filename === value.entrypoint_filename) || !value.artifacts.some((artifact) => artifact.filename === value.report_filename)) throw new Error('evidence package lacks its readable files');
    if (value.linked_capacity_run_id != null && (typeof value.linked_capacity_run_id !== 'string' || !value.linked_capacity_snapshot_digests
      || !DIGEST.test(value.linked_capacity_snapshot_digests.result)
      || Object.values(value.linked_capacity_snapshot_digests).some((digest) => digest != null && !DIGEST.test(digest)))) throw new Error('invalid linked capacity binding');
    if (value.linked_capacity_run_id == null && value.linked_capacity_snapshot_digests != null) throw new Error('unexpected linked capacity digests');
  }
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

function reportFilename(runId, capturedAt, readable = false) {
  const date = String(capturedAt).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('invalid report date');
  const [year, month, day] = date.split('-');
  return readable ? `Рободовод, отчёт от ${day}.${month}.${year}.pdf` : `Рободовод, отчёт № ${runId} от ${day}.${month}.${year}.pdf`;
}

function archiveFilename(runId, capturedAt, readable = false) {
  const date = String(capturedAt).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('invalid archive date');
  const [year, month, day] = date.split('-');
  return readable ? `Рободовод, архив расчёта от ${day}.${month}.${year}.zip` : `Рободовод, доказательства № ${runId} от ${day}.${month}.${year}.zip`;
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
    const filename = ['calculation-evidence-export-manifest-v2', 'calculation-evidence-export-manifest-v3'].includes(manifest.schema_version)
      ? archiveFilename(runId, manifest.snapshot_captured_at, manifest.schema_version.endsWith('-v3'))
      : `robomera-evidence-${runId}.zip`;
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
    this.saveImpl(blob, reportFilename(runId, manifest.snapshot_captured_at, manifest.schema_version.endsWith('-v3')));
    return manifest;
  }
}

export async function downloadEvidenceExport({ projectId, runId, session = new EvidenceExportSession() }) {
  return session.download(projectId, runId);
}
