import { assertCapacityResponse } from './capacityResultsModel.js';

const API = import.meta.env?.VITE_API_URL || '';

function errorMessage(payload, fallback) {
  if (payload?.issues?.[0]?.message) return payload.issues[0].message;
  if (typeof payload?.detail === 'string') return payload.detail;
  return fallback;
}

export function createCapacityAnalysisClient(fetchImpl = fetch) {
  let requestSequence = 0;

  const request = async (path, options, expectedRevision = null) => {
    requestSequence += 1;
    const sequence = requestSequence;
    const response = await fetchImpl(`${API}${path}`, {
      credentials: 'include',
      ...options,
      headers: {
        ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options?.headers || {}),
      },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(payload, `HTTP ${response.status}`));
    if (sequence !== requestSequence) {
      const error = new Error('STALE_CAPACITY_RESPONSE');
      error.code = 'STALE_CAPACITY_RESPONSE';
      throw error;
    }
    return assertCapacityResponse(payload, expectedRevision);
  };

  return {
    create(payload, csrfToken) {
      return request('/api/v2/capacity-analyses', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(payload),
      }, payload.input_revision);
    },
    read(runId, expectedRevision = null) {
      return request(`/api/v2/capacity-analyses/${encodeURIComponent(runId)}`, {}, expectedRevision);
    },
  };
}
