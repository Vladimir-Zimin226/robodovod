import { downloadEvidenceExport } from '../evidenceExportApi';

// Compatibility entry point: C26 delegates report content to the immutable
// server snapshot and intentionally performs no capacity or finance arithmetic.
export function generateReport({ projectId, runId }) {
  return downloadEvidenceExport({ projectId, runId });
}
