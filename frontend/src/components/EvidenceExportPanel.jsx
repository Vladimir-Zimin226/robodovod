import { useEffect, useState } from 'react';
import { EvidenceExportSession, exportErrorMessage } from '../evidenceExportApi';
import { sectionLabel, statusLabel, savedCalculationLabel } from '../presentation';

const API = import.meta.env?.VITE_API_URL || '';

export default function EvidenceExportPanel({ projectId, runId }) {
  return <EvidenceExportSource key={`${projectId}:${runId}`} projectId={projectId} runId={runId} />;
}

function EvidenceExportSource({ projectId, runId }) {
  const [session] = useState(() => new EvidenceExportSession());
  const [manifest, setManifest] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [simulations, setSimulations] = useState([]);
  const [simulationRequestId, setSimulationRequestId] = useState('');

  useEffect(() => {
    if (!projectId || !runId) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/v2/simulations/projects/${encodeURIComponent(projectId)}/analysis-runs/${encodeURIComponent(runId)}/evidence`,
      { credentials: 'include', signal: controller.signal })
      .then((response) => response.ok ? response.json() : { items: [] })
      .then((body) => {
        if (controller.signal.aborted) return;
        const items = (body.items || []).map((item) => ({ id: item.request?.request_id, digest: item.report?.replay?.report_content_digest })).filter((item) => item.id);
        setSimulations(items);
        setSimulationRequestId(items[0]?.id || '');
      }).catch(() => { if (!controller.signal.aborted) setSimulations([]); });
    return () => controller.abort();
  }, [projectId, runId]);

  useEffect(() => {
    session.loadManifest(projectId, runId, simulationRequestId || null)
      .then((next) => { setManifest(next); setStatus('ready'); })
      .catch((reason) => {
        if (reason.message !== 'stale evidence response') {
          setError(exportErrorMessage(reason));
          setStatus('error');
        }
      });
    return () => session.cancel();
  }, [projectId, runId, session, simulationRequestId]);

  const download = async () => {
    setStatus('downloading');
    setError('');
    try {
      const next = await session.download(projectId, runId, simulationRequestId || null);
      setManifest(next);
      setStatus('downloaded');
    } catch (reason) {
      if (reason.message !== 'stale evidence response') {
        setError(exportErrorMessage(reason));
        setStatus('error');
      }
    }
  };

  const downloadReport = async () => {
    setStatus('downloading-pdf');
    setError('');
    try {
      const next = await session.downloadInvestorReport(projectId, runId, simulationRequestId || null);
      setManifest(next);
      setStatus('downloaded-pdf');
    } catch (reason) {
      if (reason.message !== 'stale evidence response') {
        setError(exportErrorMessage(reason));
        setStatus('error');
      }
    }
  };

  const downloadFormat = async (format) => {
    setStatus(`downloading-${format}`); setError('');
    try {
      const next = await session.downloadFormat(projectId, runId, format, simulationRequestId || null);
      setManifest(next); setStatus(`downloaded-${format}`);
    } catch (reason) {
      if (reason.message !== 'stale evidence response') { setError(exportErrorMessage(reason)); setStatus('error'); }
    }
  };

  return (
    <section className="evidence-export-v2 panel p-4 space-y-3" aria-label="Отчёт и архив расчёта">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold">Отчёт и архив расчёта</h2>
          <p className="text-xs text-slate-500">PDF для обсуждения инвестиций: показатели, сравнение сценариев и графики с пометкой глубины расчёта. Точные значения и технические источники — в XLSX и архиве ZIP. Экспорт не пересчитывает результат.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {manifest && <a className="secondary-action" href={`${API}/api/projects/${encodeURIComponent(projectId)}/analysis-runs/${encodeURIComponent(runId)}/exports/investor-report-preview.pdf${simulationRequestId ? `?simulation_request_id=${encodeURIComponent(simulationRequestId)}` : ''}#zoom=page-width&navpanes=0`} target="_blank" rel="noreferrer">Открыть PDF</a>}
          <button className="primary-action" disabled={!manifest || status.startsWith('downloading')} onClick={downloadReport}>
            {status === 'downloading-pdf' ? 'Формируем отчёт…' : 'Скачать инвестиционный отчёт PDF'}
          </button>
          <button className="secondary-action" disabled={!manifest || status.startsWith('downloading')} onClick={() => downloadFormat('xlsx')}>Скачать XLSX</button>
          <button className="secondary-action" disabled={!manifest || status.startsWith('downloading')} onClick={() => downloadFormat('csv')}>Скачать CSV</button>
          {manifest?.visualization_filename && <button className="secondary-action" disabled={status.startsWith('downloading')} onClick={() => downloadFormat('svg')}>Скачать 2D SVG</button>}
          <button className="primary-action" disabled={!manifest || status.startsWith('downloading')} onClick={download}>
            {status === 'downloading' ? 'Формируем архив…' : 'Скачать архив ZIP'}
          </button>
        </div>
      </div>
      {simulations.length > 0 && <label className="block text-sm">Сохранённая симуляция для PDF и пакета
        <select value={simulationRequestId} onChange={(event) => {
          session.cancel(); setManifest(null); setError(''); setStatus('loading');
          setSimulationRequestId(event.target.value);
        }}>
          {simulations.map((item, index) => <option key={item.id} value={item.id}>Сохранённая симуляция {index + 1}</option>)}
        </select>
      </label>}
      {manifest && (
        <div className="text-xs text-slate-500">
          <p>{savedCalculationLabel(manifest.snapshot_captured_at)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {manifest.sections.map((section) => (
              <span key={section.name} className={section.status === 'AVAILABLE' ? 'text-emerald-700' : 'text-amber-700'}>
                {sectionLabel(section.name)}: {statusLabel(section.status)}
              </span>
            ))}
          </div>
          {manifest.schema_version.endsWith('-v4') && <p>PDF, XLSX и CSV построены из одного сохранённого результата. {manifest.simulation_request_id ? 'Сохранённая симуляция включена.' : 'Сохранённая симуляция пока не выбрана.'}</p>}
          <p>Контрольные суммы и версии доступны в архиве ZIP.</p>
        </div>
      )}
      {status === 'downloaded' && <p className="text-xs text-emerald-700">Архив скачан и связан с сохранённым расчётом.</p>}
      {status === 'downloaded-pdf' && <p className="text-xs text-emerald-700">Отчёт скачан и связан с сохранённым результатом.</p>}
      {status.startsWith('downloaded-') && status !== 'downloaded-pdf' && <p className="text-xs text-emerald-700">Файл скачан и связан с сохранённым расчётом.</p>}
      {error && <p role="alert" className="text-xs text-red-700">Экспорт недоступен: {error}</p>}
    </section>
  );
}
