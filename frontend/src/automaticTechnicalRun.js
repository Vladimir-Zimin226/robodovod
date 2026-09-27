import { buildPartialEconomicsRunRequest } from './economicsInputV2.js';
import { buildTechnicalSimulationRequest } from './economicsSimulationRequest.js';
import { readCsrfCookie } from './persistenceApi.js';

const pending = new Map();
// Share an in-flight save across React StrictMode mounts. Failed requests may retry.
export function automaticTechnicalRun({ project, capacityRequest, capacityRunId, startTime, timezone }, request = fetch) {
  const [hours, minutes] = startTime.split(':').map(Number);
  if (!startTime || !Number.isInteger(hours) || !Number.isInteger(minutes) || hours > 23 || minutes > 59 || !timezone.trim()) {
    return Promise.reject(new Error('Выберите местное начало работы и часовой пояс.'));
  }
  const body = buildPartialEconomicsRunRequest({ values: { capacityRunId,
    startSeconds: String(hours * 3600 + minutes * 60), timezone: timezone.trim() },
  capacityRequest, project, scenario: project?.scenarios?.find((item) => item.slot === 'BASE') });
  const key = JSON.stringify([project.id, body]);
  if (!pending.has(key)) {
    const promise = (async () => {
      const api = import.meta.env?.VITE_API_URL || '';
      const base = `${api}/api/projects/${encodeURIComponent(project.id)}/analysis-runs`;
      const listing = await request(base, { credentials: 'include' });
      if (listing.ok) {
        const { items = [] } = await listing.json();
        for (const item of items.filter((row) => row.run_kind === 'FULL_ANALYSIS' && row.status === 'SUCCEEDED')) {
          const response = await request(`${base}/${encodeURIComponent(item.id)}`, { credentials: 'include' });
          if (!response.ok) continue;
          const run = await response.json();
          const input = run.input_snapshot;
          if (input?.capacity_run_id === capacityRunId && input.economics?.timezone === timezone.trim()
            && String(input.economics?.start_seconds_from_midnight) === body.input.start_seconds_from_midnight
            && buildTechnicalSimulationRequest(run)) return run;
        }
      }
      const response = await request(`${api}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.issues?.[0]?.next_step || (typeof payload.detail === 'string' ? payload.detail : 'Не удалось сохранить симуляцию.'));
      return payload;
    })().catch((failure) => { pending.delete(key); throw failure; });
    pending.set(key, promise);
  }
  return pending.get(key);
}
