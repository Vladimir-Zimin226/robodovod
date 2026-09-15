import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { parentMessage, parseRobCraftMessage } from '../robcraftProtocol';

const LOAD_TIMEOUT_MS = 12000;

export default function RobCraftFrame({ scenarioSpec, compact = false }) {
  const iframeRef = useRef(null);
  const requestCounter = useRef(0);
  const activeRequest = useRef(null);
  const [ready, setReady] = useState(false);
  const [appliedRevision, setAppliedRevision] = useState(null);
  const [error, setError] = useState(null);
  const [cameraMode, setCameraMode] = useState('AUTOPILOT');
  const [editorEnabled, setEditorEnabled] = useState(false);
  const [scenePatch, setScenePatch] = useState({ status: 'CLEAN', summary: null, zoneId: null });
  const [manualNotice, setManualNotice] = useState(null);
  const revisionId = scenarioSpec?.revision_id || null;
  const visualizationOnly = Boolean(scenarioSpec?.zones?.some((zone) =>
    zone.status === 'NO_ACCEPTABLE_ECONOMICS'
      && scenarioSpec.fleet?.some((item) => item.zone_id === zone.id)));
  const synchronizing = Boolean(revisionId && appliedRevision !== revisionId && !error);

  const post = (message) => {
    iframeRef.current?.contentWindow?.postMessage(message, window.location.origin);
  };

  useEffect(() => {
    const onMessage = (event) => {
      if (event.origin !== window.location.origin || event.source !== iframeRef.current?.contentWindow) return;
      try {
        const message = parseRobCraftMessage(event.data);
        if (message.type === 'ROBCRAFT_READY') {
          setReady(true);
          setAppliedRevision(null);
          setEditorEnabled(false);
          setScenePatch({ status: 'CLEAN', summary: null, zoneId: null });
          setError(null);
          return;
        }
        if (message.type === 'ROBCRAFT_ERROR') {
          if (!activeRequest.current || message.request_id === activeRequest.current.requestId || message.request_id === null) {
            setError(message.payload.message);
          }
          return;
        }
        const current = activeRequest.current;
        if (!current || message.request_id !== current.requestId || message.revision_id !== current.revisionId) return;
        if (message.type === 'CAMERA_MODE_CHANGED') {
          setCameraMode(message.payload.mode);
          setManualNotice(message.payload.reason === 'POINTER_LOCK_UNAVAILABLE'
            ? 'Браузер не разрешил захват указателя. Автопоказ продолжен.'
            : message.payload.reason === 'GROUND_POSITION_BLOCKED'
              ? 'Для перехода на уровень пола перелетите в свободный проход и снова нажмите F.'
              : null);
          return;
        }
        if (message.type === 'EDITOR_MODE_CHANGED') {
          setEditorEnabled(message.payload.enabled);
          setScenePatch((currentPatch) => ({ ...currentPatch, status: message.payload.scene_status }));
          return;
        }
        if (message.type === 'SCENE_PATCH_CHANGED') {
          setScenePatch({ status: message.payload.status, summary: message.payload.summary, zoneId: message.payload.zone_id });
          return;
        }
        if (message.payload.status === 'PREPARED') {
          post(parentMessage('APPLY_REVISION', current.revisionId, current.requestId));
        } else {
          setAppliedRevision(current.revisionId);
          setError(null);
        }
      } catch (protocolError) {
        setError(`Нарушен протокол RobCraft: ${protocolError.message}`);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  useLayoutEffect(() => {
    if (!ready || !scenarioSpec || !revisionId || appliedRevision === revisionId) return;
    requestCounter.current += 1;
    const requestId = `request_${Date.now()}_${requestCounter.current}`;
    activeRequest.current = { requestId, revisionId };
    post(parentMessage('LOAD_SCENARIO', revisionId, requestId, { scenario_spec: scenarioSpec }));
  }, [ready, scenarioSpec, revisionId, appliedRevision]);

  useEffect(() => {
    if (!synchronizing) return undefined;
    const timeout = window.setTimeout(() => {
      setError('RobCraft не подтвердил загрузку сцены. Экономический расчёт остаётся доступен.');
    }, LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [synchronizing, revisionId]);

  return (
    <section className={`robcraft-frame ${compact ? 'is-compact' : ''}`} aria-label="3D-сценарий RobCraft">
      <div className="robcraft-frame-header flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 text-white">
        <div>
          <div className="text-sm font-semibold">RobCraft · сценарная 3D-симуляция</div>
          <div className="text-[11px] text-slate-400">Концептуальная визуализация · ревизия {revisionId || 'не получена'}{scenePatch.zoneId ? ` · зона ${scenePatch.zoneId}` : ''}</div>
          {visualizationOnly && <div className="mt-1 text-[10px] font-semibold text-amber-300">ТЕХНИЧЕСКИЙ ВАРИАНТ · НЕ ЭКОНОМИЧЕСКАЯ РЕКОМЕНДАЦИЯ</div>}
        </div>
        <div className="text-right">
          {scenePatch.status === 'MODIFIED' && (
            <div className="mb-2 rounded border border-amber-300/30 bg-amber-300/10 px-3 py-1 text-[10px] font-semibold text-amber-200">
              ИЗМЕНЁННАЯ СЦЕНА · ЭКОНОМИКА НЕ ПЕРЕСЧИТАНА
            </div>
          )}
          <span className={`rounded-full px-3 py-1 text-[10px] font-semibold ${cameraMode === 'MANUAL_FIRST_PERSON' ? 'bg-sky-400/10 text-sky-300' : 'bg-emerald-400/10 text-emerald-300'}`}>
            {editorEnabled ? 'РЕДАКТОР · СИМУЛЯЦИЯ НА ПАУЗЕ' : cameraMode === 'MANUAL_FIRST_PERSON' ? 'РУЧНОЙ ОСМОТР' : 'АВТОПОКАЗ'}
          </span>
          {manualNotice && <div className="mt-2 text-[10px] text-amber-300">{manualNotice}</div>}
        </div>
      </div>
      <div className="relative aspect-video min-h-[320px] max-h-[680px] w-full">
        <iframe
          ref={iframeRef}
          src="/robcraft/?embedded=1"
          title="RobCraft — 3D-сценарий роботизации"
          className="h-full w-full border-0"
          allow="fullscreen"
          allowFullScreen
          onLoad={() => setError(null)}
          onError={() => setError('Не удалось загрузить RobCraft. Экономический расчёт остаётся доступен.')}
        />
        {(synchronizing || !scenarioSpec) && !error && (
          <div className="absolute inset-0 grid place-items-center bg-slate-950/95 px-6 text-center text-sm text-slate-300">
            {scenarioSpec ? 'Синхронизируем 3D-сцену с расчётом…' : 'Для этого результата нет ScenarioSpec.'}
          </div>
        )}
        {error && (
          <div className="absolute inset-0 grid place-items-center bg-slate-950 px-6 text-center">
            <div><div className="text-sm font-semibold text-amber-300">3D-сцена недоступна</div><p className="mt-2 max-w-xl text-xs leading-5 text-slate-400">{error}</p></div>
          </div>
        )}
      </div>
    </section>
  );
}
