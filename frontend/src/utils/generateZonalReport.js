import { downloadEvidenceExport } from '../evidenceExportApi';

// Compatibility entry point: the persisted server snapshot is the sole source.
export function generateZonalReport({ projectId, runId }) {
  return downloadEvidenceExport({ projectId, runId });
}
