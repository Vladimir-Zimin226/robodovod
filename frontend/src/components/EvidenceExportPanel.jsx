import { useEffect, useState } from 'react';
import { EvidenceExportSession } from '../evidenceExportApi';

export default function EvidenceExportPanel({ projectId, runId }) {
  const [session] = useState(() => new EvidenceExportSession());
  const [manifest, setManifest] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    session.loadManifest(projectId, runId)
      .then((next) => { setManifest(next); setStatus('ready'); })
      .catch((reason) => {
        if (reason.message !== 'stale evidence response') {
          setError(reason.message);
          setStatus('error');
        }
      });
    return () => session.cancel();
  }, [projectId, runId, session]);

  const download = async () => {
    setStatus('downloading');
    setError('');
    try {
      const next = await session.download(projectId, runId);
      setManifest(next);
      setStatus('downloaded');
    } catch (reason) {
      if (reason.message !== 'stale evidence response') {
        setError(reason.message);
        setStatus('error');
      }
    }
  };

  const downloadReport = async () => {
    setStatus('downloading-pdf');
    setError('');
    try {
      const next = await session.downloadReport(projectId, runId);
      setManifest(next);
      setStatus('downloaded-pdf');
    } catch (reason) {
      if (reason.message !== 'stale evidence response') {
        setError(reason.message);
        setStatus('error');
      }
    }
  };

  return (
    <section className="evidence-export-v2 panel p-4 space-y-3" aria-label="Доказательный экспорт расчёта">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold">Архив доказательств</h2>
          <p className="text-xs text-slate-500">В ZIP откройте «НАЧНИТЕ_ЗДЕСЬ.md»: там путь к читаемому PDF, объяснение CSV и контрольные суммы. Экспорт не пересчитывает результат.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="primary-action" disabled={!manifest || status.startsWith('downloading')} onClick={downloadReport}>
            {status === 'downloading-pdf' ? 'Формируем отчёт…' : 'Скачать читаемый отчёт PDF'}
          </button>
          <button className="primary-action" disabled={!manifest || status.startsWith('downloading')} onClick={download}>
            {status === 'downloading' ? 'Формируем архив…' : 'Скачать архив ZIP'}
          </button>
        </div>
      </div>
      {manifest && (
        <div className="text-xs text-slate-500">
          Run {manifest.run_id} · revision {manifest.revision_id || 'NOT_AVAILABLE'} · digest {manifest.manifest_digest}
          <div className="mt-2 flex flex-wrap gap-2">
            {manifest.sections.map((section) => (
              <span key={section.name} className={section.status === 'AVAILABLE' ? 'text-emerald-700' : 'text-amber-700'}>
                {section.name}: {section.status}
              </span>
            ))}
          </div>
        </div>
      )}
      {status === 'downloaded' && <p className="text-xs text-emerald-700">Архив скачан и связан с показанным digest.</p>}
      {status === 'downloaded-pdf' && <p className="text-xs text-emerald-700">Отчёт скачан и связан с сохранённым результатом.</p>}
      {error && <p role="alert" className="text-xs text-red-700">Экспорт недоступен: {error}</p>}
    </section>
  );
}
