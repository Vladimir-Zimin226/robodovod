const LEGACY = 'legacy-economics-v1';
const V2 = 'economics-runtime-v2';

export function economicsRunView(run) {
  if (!run || run.run_kind !== 'FULL_ANALYSIS') return null;
  const version = run.versions?.economics;
  const mapping = run.economics_runtime;
  if (!mapping || mapping.economics_version !== version) {
    throw new TypeError('ECONOMICS_VERSION_MAPPING_MISMATCH');
  }
  if (version === LEGACY) {
    if (mapping.viewer_version !== 'legacy-snapshot-viewer-v1' || mapping.replay_mode !== 'SAVED_SNAPSHOT_ONLY') {
      throw new TypeError('LEGACY_VIEWER_MAPPING_INVALID');
    }
    return { viewer: 'LEGACY_SNAPSHOT', label: 'Legacy snapshot', notice: mapping.migration_notice };
  }
  if (version === V2) {
    if (mapping.viewer_version !== 'commercial-scenarios-viewer-v2') {
      throw new TypeError('V2_VIEWER_MAPPING_INVALID');
    }
    return { viewer: 'COMMERCIAL_SCENARIOS_V2', label: 'Economics v2', notice: mapping.migration_notice };
  }
  throw new TypeError('UNSUPPORTED_ECONOMICS_VERSION');
}
