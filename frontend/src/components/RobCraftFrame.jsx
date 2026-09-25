import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { negotiateScenarioSpec, parentMessage, parseRobCraftMessage } from '../robcraftProtocol';

const LOAD_TIMEOUT_MS = 12000;

export default function RobCraftFrame({ scenarioSpec, simulationReport = null, compact = false, selectedZoneId = null, onZoneChange = null }) {
  const iframeRef = useRef(null);
  const requestCounter = useRef(0);
  const activeRequest = useRef(null);
  const zoneSyncReady = useRef(false);
  const onZoneChangeRef = useRef(onZoneChange);
  const [ready, setReady] = useState(false);
  const [capabilities, setCapabilities] = useState([]);
  const [appliedRevision, setAppliedRevision] = useState(null);
  const [error, setError] = useState(null);
  const [cameraMode, setCameraMode] = useState('AUTOPILOT');
  const [editorEnabled, setEditorEnabled] = useState(false);
  const [scenePatch, setScenePatch] = useState({ status: 'CLEAN', summary: null, zoneId: null });
  const [manualNotice, setManualNotice] = useState(null);
  const [rendererReport, setRendererReport] = useState(null);
  const revisionId = scenarioSpec?.revision_id || null;
  const reportDigest = simulationReport?.replay?.report_content_digest || 'no-report';
  const bindingKey = revisionId ? `${revisionId}:${reportDigest}` : null;
  const negotiationError = useMemo(() => {
    if (!ready || !scenarioSpec) return null;
    try { negotiateScenarioSpec(scenarioSpec, capabilities); return null; } catch (failure) { return failure.message; }
  }, [ready, scenarioSpec, capabilities]);
  const visibleError = error || negotiationError;
  const visualizationOnly = Boolean(scenarioSpec?.zones?.some((zone) =>
    zone.status === 'NO_ACCEPTABLE_ECONOMICS'
      && scenarioSpec.fleet?.some((item) => item.zone_id === zone.id)));
  const synchronizing = Boolean(bindingKey && appliedRevision !== bindingKey && !visibleError);

  const post = (message) => {
    iframeRef.current?.contentWindow?.postMessage(message, window.location.origin);
  };

  useEffect(() => { onZoneChangeRef.current = onZoneChange; }, [onZoneChange]);

  useEffect(() => {
    const onMessage = (event) => {
      if (event.origin !== window.location.origin || event.source !== iframeRef.current?.contentWindow) return;
      try {
        const message = parseRobCraftMessage(event.data);
        if (message.type === 'ROBCRAFT_READY') {
          setCapabilities(message.payload.capabilities);
          setReady(true);
          setAppliedRevision(null);
          zoneSyncReady.current = false;
          setEditorEnabled(false);
          setScenePatch({ status: 'CLEAN', summary: null, zoneId: null });
          setError(null);
          setRendererReport(null);
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
          setError(null);
          if (zoneSyncReady.current) onZoneChangeRef.current?.(message.payload.zone_id);
          return;
        }
        if (message.type === 'ROBCRAFT_REPORT') {
          if (current.reportDigest !== 'no-report' && message.payload.bindings.authoritative_report_digest !== current.reportDigest) {
            setError('Трёхмерная сцена вернула устаревший отчёт симуляции. Повторите загрузку.');
            return;
          }
          setRendererReport(message.payload);
          return;
        }
        if (message.payload.status === 'PREPARED') {
          post(parentMessage('APPLY_REVISION', current.revisionId, current.requestId));
        } else {
          setAppliedRevision(current.bindingKey);
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
    if (!ready || !scenarioSpec || !revisionId || appliedRevision === bindingKey) return;
    if (negotiationError) return;
    requestCounter.current += 1;
    const requestId = `request_${Date.now()}_${requestCounter.current}`;
    zoneSyncReady.current = false;
    activeRequest.current = { requestId, revisionId, reportDigest, bindingKey };
    post(parentMessage('LOAD_SCENARIO', revisionId, requestId, { scenario_spec: scenarioSpec, simulation_report: simulationReport }));
  }, [ready, capabilities, negotiationError, scenarioSpec, simulationReport, revisionId, reportDigest, bindingKey, appliedRevision]);

  useEffect(() => {
    const current = activeRequest.current;
    if (!selectedZoneId || appliedRevision !== bindingKey || current?.bindingKey !== bindingKey) return;
    zoneSyncReady.current = true;
    post(parentMessage('SELECT_ZONE', current.revisionId, current.requestId, { zone_id: selectedZoneId }));
  }, [appliedRevision, bindingKey, selectedZoneId]);

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
          <div className="text-[11px] text-slate-400">Концептуальная визуализация{scenePatch.zoneId ? ` · зона ${scenePatch.zoneId}` : ''}<details><summary>Технические подробности</summary>Версия ввода: {revisionId || 'не получена'}</details></div>
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
        {(synchronizing || !scenarioSpec) && !visibleError && (
          <div className="absolute inset-0 grid place-items-center bg-slate-950/95 px-6 text-center text-sm text-slate-300">
            {scenarioSpec ? 'Синхронизируем 3D-сцену с расчётом…' : 'Для этого результата нет ScenarioSpec.'}
          </div>
        )}
        {visibleError && (
          <div className="absolute inset-0 grid place-items-center bg-slate-950 px-6 text-center">
            <div><div className="text-sm font-semibold text-amber-300">3D-сцена недоступна</div><p className="mt-2 max-w-xl text-xs leading-5 text-slate-400">{visibleError}</p></div>
          </div>
        )}
      </div>
      {rendererReport && (
        <div className="border-t border-white/10 bg-slate-950 px-4 py-3 text-[11px] leading-5 text-slate-300">
          <strong className="text-sky-300">LOCAL VISUAL OBSERVATION ONLY</strong>
          {' · '}t={Number(rendererReport.measurement_basis.elapsed_seconds).toFixed(1)} s
          {' · '}moving {Number(rendererReport.utilization.moving_percent).toFixed(1)}% (не productive utilization)
          {' · '}условная пропускная способность сцены {Number(rendererReport.observed.throughput_units_per_hour).toFixed(1)} {rendererReport.observed.throughput_unit} (не показатель симуляции)
          <div className="text-amber-300">SLA: NOT_EVALUATED · energy: arbitrary renderer units · failures/charging: visual demo only · не инженерная сертификация.</div>
        </div>
      )}
    </section>
  );
}
