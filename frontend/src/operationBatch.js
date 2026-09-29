import { buildDemoCapacityRequest, demoCandidates } from './demoCapacityFlow.js';

async function json(fetcher, url, options = {}) {
  const response = await fetcher(url, { credentials: 'include', ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
  return body;
}

export async function calculateOperationBatch({ fetcher = fetch, api = '', normalized, draft, projectId, acknowledged, csrf, batchId = crypto.randomUUID(), resumeOperations = [], onCheckpoint = () => {}, onProgress = () => {} }) {
  if (!acknowledged) throw new Error('Подтвердите предварительные допущения.');
  if (!projectId || normalized?.response?.input_revision !== draft.inputRevision) throw new Error('Нормализуйте текущую ревизию проекта.');
  const processes = normalized.response.normalized_processes.filter(item => item.active);
  if (!processes.length) throw new Error('Нет выбранных операций.');
  const headers = { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf };
  const operations = [];
  const resumed = new Map(resumeOperations.map(row => [row.process.process_id, row]));
  for (const process of processes) {
    if (draft.inputRevision !== normalized.response.input_revision) throw new Error('Ввод изменён во время расчёта. Нормализуйте его заново.');
    const zone = draft.zones.find(item => process.process_id.startsWith(`${item.zoneId}.`));
    if (!zone) throw new Error(`Не найдена зона процесса ${process.process_id}`);
    if (resumed.has(process.process_id)) {
      operations.push(resumed.get(process.process_id));
      onProgress(operations.length, processes.length);
      continue;
    }
    const row = { process, zone_id: zone.zoneId, zone_label: zone.label };
    const block = reason => { operations.push({ ...row, blocker: reason }); onCheckpoint([...operations]); onProgress(operations.length, processes.length); };
    if (!['TRANSPORT_CYCLE', 'DELIVERY_CYCLE', 'CLEANING_AREA'].includes(process.scope)) {
      block('Для этого профиля пока нет утверждённой формулы мощности. Операция сохранена как непокрытая.');
      continue;
    }
    const source = draft.processes.find(item => item.processId === process.process_id);
    let capacity;
    {
      const params = new URLSearchParams({ object_kind: process.object_kind.toLowerCase(), process_code: process.process_code });
      if (process.item_mass?.status === 'KNOWN') params.set('max_payload_kg', process.item_mass.normalized_value);
      const catalog = await json(fetcher, `${api}/api/v2/capacity-catalog/positions?${params}`);
      const candidates = demoCandidates(catalog.items || [], process.scope);
      if (!candidates.length) { block('В активном каталоге нет расчётной модели для этого физического профиля.'); continue; }
      try {
        capacity = buildDemoCapacityRequest({ normalized, projectId, processId: process.process_id,
          position: candidates[0], exchangeSeconds: source?.exchangeSeconds,
          cleaningFrequency: source?.cleaningFrequency ?? '1', acknowledged, zone });
      } catch (error) { block(`Не хватает входов для отдельного расчёта: ${error.message}`); continue; }
      const preview = await json(fetcher, `${api}/api/candidate-comparisons/preview`, {
        method: 'POST', headers, body: JSON.stringify({ capacity_request: capacity }),
      });
      const eligible = preview.candidates?.filter(item => item.status !== 'EXCLUDED' && item.status !== 'INFORMATION_ONLY') || [];
      const recommended = preview.technical_recommendation?.position_id;
      const ranked = eligible.filter(item => item.technical_score != null)
        .sort((a, b) => Number(b.technical_score) - Number(a.technical_score) || a.position_id.localeCompare(b.position_id));
      const chosen = candidates.find(item => item.position_id === recommended && eligible.some(row => row.position_id === recommended))
        || candidates.find(item => item.position_id === ranked[0]?.position_id);
      if (!chosen) {
        block(`Нет обоснованной технической рекомендации для автоматического выбора: ${preview.candidates?.flatMap(item => item.constraints?.checks || []).filter(check => check.status === 'FAIL').map(check => check.reason_code).slice(0, 3).join('; ') || 'проверка пригодности или оценка отсутствует'}.`);
        continue;
      }
      capacity = { ...capacity, model_id: chosen.model_id, position_id: chosen.position_id };
    }
    const saved = await json(fetcher, `${api}/api/v2/capacity-analyses`, { method: 'POST', headers, body: JSON.stringify(capacity) });
    operations.push({ ...row, run_id: saved.run_id });
    onCheckpoint([...operations]);
    onProgress(operations.length, processes.length);
  }
  const summary = await json(fetcher, `${api}/api/v2/projects/${encodeURIComponent(projectId)}/operation-batches`, {
    method: 'POST', headers, body: JSON.stringify({ batch_id: batchId, input_revision: draft.inputRevision, operations }),
  });
  return summary;
}
