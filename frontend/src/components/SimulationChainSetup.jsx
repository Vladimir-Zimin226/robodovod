import { useEffect, useState } from 'react';
import { buildExtendedSimulationRequest } from '../warehouseSimulationChain';

const API = import.meta.env.VITE_API_URL || '';
const LABELS = [
  ['PICKING', 'Отбор'], ['BUFFER', 'Буфер'],
  ['FEED_TO_PACK', 'Подача к упаковке'], ['PACKAGING', 'Упаковка'],
];

export default function SimulationChainSetup({ baseRequest, onStart }) {
  const [envelope, setEnvelope] = useState(null);
  const [rates, setRates] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!baseRequest?.project_id) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/warehouse-chain/projects/${encodeURIComponent(baseRequest.project_id)}`, {
      credentials: 'include', signal: controller.signal,
    }).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Цепочка склада недоступна: HTTP ${response.status}`)))
      .then(setEnvelope).catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, [baseRequest?.project_id]);

  if (!envelope?.chain || envelope.chain.version < 1 || baseRequest?.scenario_spec?.profile?.calculation_profile !== 'TRANSPORT_CYCLE_V1') return null;
  const start = async () => {
    setError(''); setBusy(true);
    try {
      const request = await buildExtendedSimulationRequest(baseRequest, envelope, rates);
      if (!request) throw new Error('Для расчёта стадии нужны подтверждённый поток, связь с паллетной отгрузкой, мощность ресурса и отдельная скорость. Суточный объём должен совпадать с перевозкой.');
      onStart(request);
    } catch (reason) { setError(reason.message); }
    finally { setBusy(false); }
  };
  return <details className="simulation-chain-setup rounded border p-3 text-sm">
    <summary>Расширенная цепочка склада · версия {envelope.chain.version}</summary>
    <p>Стадии добавляются только по подтверждённым потокам и связям из модели склада. Скорость каждой станции задайте отдельно в единицах её потока за час. Неполные стадии останутся внешней границей; их труд не включается в экономику паллетной перевозки.</p>
    <div className="mt-2 grid gap-2 sm:grid-cols-2">{LABELS.map(([code, label]) => {
      const flow = envelope.chain.flows.find((item) => (code === 'PICKING'
        ? ['picking_lines', 'picking_items'].includes(item.code)
        : item.code === (code === 'PACKAGING' ? 'packaging' : 'tote_handoff')) && item.confirmed);
      return <label key={code}>{label} · {flow?.unit?.replace('/day', '/ч') || 'единиц потока/ч'}<input type="number" min="0.001" step="any" value={rates[code] || ''} onChange={(event) => setRates((current) => ({ ...current, [code]: event.target.value }))} className="block w-full rounded border p-2" placeholder="Не задано" /></label>;
    })}</div>
    {error && <p role="alert" className="text-red-300">{error}</p>}
    <button type="button" className="secondary-action mt-2" disabled={busy} onClick={start}>{busy ? 'Готовим сценарий…' : 'Рассчитать введённые стадии'}</button>
  </details>;
}
