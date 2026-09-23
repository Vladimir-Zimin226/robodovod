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

  return (
    <section className="panel p-4 space-y-3" aria-label="Доказательный экспорт расчёта">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold">Доказательный экспорт</h2>
          <p className="text-xs text-slate-500">PDF, CSV-разделы и полный неизменяемый snapshot — без пересчёта в браузере.</p>
        </div>
        <button className="primary-action" disabled={!manifest || status === 'downloading'} onClick={download}>
          {status === 'downloading' ? 'Формируем архив…' : 'Скачать evidence ZIP'}
        </button>
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
      {error && <p role="alert" className="text-xs text-red-700">Экспорт недоступен: {error}</p>}
    </section>
  );
}
