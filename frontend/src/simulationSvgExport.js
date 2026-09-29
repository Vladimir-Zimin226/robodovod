import { parseSimulationBundle } from './simulation2dModel.js';
import { physicalInputs } from './physicalScenario.js';
import { LIVE_PLAYBACK_VERSION } from '../../robcraft/src/integration/safe-playback-v2.js';
import { humanizePresentation } from './presentation.js';

// Reusable by the report package: a frame plus the exact saved source, no calculation.
export function visualExportMetadata(request, report, analysisRunId, simulationTimeUs, zoneId, date, playbackVersion = null) {
  const { spec } = parseSimulationBundle(request, report);
  return {
    schema_version: playbackVersion ? 'simulation-visual-export-v2' : 'simulation-visual-export-v1', exported_at: date,
    ...(playbackVersion ? {playback_version: playbackVersion} : {}),
    analysis_run_id: analysisRunId, capacity_run_id: spec.analysis.capacity_run_id,
    scenario_revision_id: spec.revision_id, scenario_spec_digest: report.replay.scenario_spec_digest,
    report_id: report.report_id, report_content_digest: report.replay.report_content_digest,
    canonical_request_digest: report.replay.canonical_request_digest,
    simulation_time_us: simulationTimeUs, zone_id: zoneId,
    request, report,
  };
}

export function serializeSimulationSvg(source, metadata, label) {
  if (!source || source.tagName.toLowerCase() !== 'svg') throw new TypeError('Нет открытого 2D-кадра');
  const doc = source.ownerDocument;
  const ns = 'http://www.w3.org/2000/svg';
  const create = (name) => doc.createElementNS(ns, name);
  const root = create('svg');
  const lines = metadata.playback_version === LIVE_PLAYBACK_VERSION ? [
    `РОБОДОВОД · ${label}`, `Дата: ${metadata.exported_at} · кадр: ${metadata.simulation_time_us / 1e6} с`,
    ...physicalInputs(metadata.request.scenario_spec).map(humanizePresentation),
    `Сохранённый прогон: парк ${metadata.report.workload.fleet_units} роботов; максимальная очередь ${metadata.report.queue.maximum_jobs} заданий.`,
    'Условные безопасные маршруты. Визуальные задержки не заменяют сохранённые серверные показатели.',
    'Полные связи, версии и контрольные суммы сохранены в метаданных файла.',
  ] : [
    `РОБОДОВОД · ${label}`, `Дата: ${metadata.exported_at} · кадр: ${metadata.simulation_time_us / 1e6} с · зона: ${metadata.zone_id || 'все'}`,
    `Расчёт: ${metadata.analysis_run_id || 'демо'} · C11: ${metadata.capacity_run_id}`,
    ...physicalInputs(metadata.request.scenario_spec),
    `C23: ${metadata.report_id} · сценарий: ${metadata.scenario_revision_id}`,
    `Отчёт: ${metadata.report_content_digest}`, `ScenarioSpec: ${metadata.scenario_spec_digest}`,
    `Парк: ${metadata.report.workload.fleet_units} · спрос: ${metadata.report.capacity.required_per_hour} · выполнено: ${metadata.report.capacity.observed_per_hour} ${metadata.report.capacity.unit}`,
    `Очередь: ${metadata.report.queue.maximum_jobs} · ожидание p95: ${metadata.report.queue.p95_wait_seconds} с · ${metadata.report.capacity.verdict}`,
    'Координаты условные. Зарядка учтена агрегированно; точка условная, цикл не моделируется.',
    'Предварительная симуляция. CONSISTENT означает согласованность модели, требуется обследование объекта.',
  ].flatMap((line) => line.match(/.{1,115}/gu) || ['']);
  const header = 30 + lines.length * 22;
  const [, , width, height] = source.getAttribute('viewBox').split(/\s+/).map(Number);
  const sceneHeight = Math.round(height / width * 1200);
  root.setAttribute('viewBox', `0 0 1200 ${header + sceneHeight}`);
  root.setAttribute('width', '1200'); root.setAttribute('height', String(header + sceneHeight));
  const title = create('title'); title.textContent = label; root.append(title);
  const data = create('metadata'); data.textContent = JSON.stringify(metadata); root.append(data);
  const background = create('rect');
  background.setAttribute('width', '100%'); background.setAttribute('height', '100%'); background.setAttribute('fill', '#142027'); root.append(background);
  lines.forEach((line, index) => {
    const text = create('text'); text.setAttribute('x', '20'); text.setAttribute('y', String(26 + index * 22));
    text.setAttribute('fill', '#eef6f8'); text.setAttribute('font-family', 'Arial, sans-serif'); text.setAttribute('font-size', '16'); text.textContent = line; root.append(text);
  });
  const clone = source.cloneNode(true);
  const originals = [source, ...source.querySelectorAll('*')];
  [clone, ...clone.querySelectorAll('*')].forEach((element, index) => {
    const style = doc.defaultView.getComputedStyle(originals[index]);
    for (const property of ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'opacity', 'font-family', 'font-size', 'font-weight', 'text-anchor']) element.style.setProperty(property, style.getPropertyValue(property));
  });
  clone.setAttribute('x', '0'); clone.setAttribute('y', String(header));
  clone.setAttribute('width', '1200'); clone.setAttribute('height', String(sceneHeight));
  root.append(clone);
  return new XMLSerializer().serializeToString(root);
}

export function downloadSimulationSvg(svg, metadata, label) {
  const content = serializeSimulationSvg(svg, metadata, label);
  const url = URL.createObjectURL(new Blob([content], { type: 'image/svg+xml;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url;
  link.download = `simulation-${metadata.scenario_revision_id}-${metadata.report_content_digest.slice(7, 19)}.svg`;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
