import { itemSize } from './facilityLayout.js';
import { readCsrfCookie } from './persistenceApi.js';

const API = import.meta.env?.VITE_API_URL || '';

export function savedLayoutPayload(evidence) {
  const plan = evidence.facilityPlan;
  return { process_id: evidence.processId, applied_distance_m: String(evidence.appliedDistanceM),
    layout: { schema_version: 'facility-layout-v1', source: plan.source,
      width_m: Number(plan.width_m), depth_m: Number(plan.depth_m), robot_width_m: Number(plan.robot_width_m) || 1,
      reference_note: plan.reference_note || null, image_not_embedded: Boolean(plan.imageData),
      items: (plan.items || []).map((item, index) => {
        const [w, h] = itemSize(item);
        return { id: item.id || `item-${index}`, kind: item.kind, x: Number(item.x), y: Number(item.y),
          width_m: w, depth_m: h, provenance: item.provenance || 'DRAWN' };
      }) } };
}

export async function saveLayoutEvidence(projectId, runId, evidence) {
  const response = await fetch(`${API}/api/facility-layout/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
    body: JSON.stringify(savedLayoutPayload(evidence)),
  });
  if (!response.ok) throw new Error(`Схема не сохранена с расчётом (HTTP ${response.status}). Скачайте её JSON из конструктора.`);
  return (await response.json()).snapshot;
}

export async function loadLayoutEvidence(projectId, runId, signal) {
  const response = await fetch(`${API}/api/facility-layout/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}`, {
    credentials: 'include', signal,
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Не удалось открыть схему расчёта (HTTP ${response.status}).`);
  return (await response.json()).snapshot;
}
