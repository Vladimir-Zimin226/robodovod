import { useEffect, useRef, useState } from 'react';

const SHOTS = [
  ['Фасад и объект', 'Геометрия сцены условная. План конкретного склада не загружен.'],
  ['Робот и маршрут', '3D показывает перевозку подготовленной паллеты. Координаты служат для иллюстрации.'],
  ['Нагрузка и очередь', 'Парк и очередь взяты из сохранённого физического расчёта выбранного варианта.'],
  ['Деньги и ограничения', 'Денежный результат относится к этой операции и основан на сценарных ценах.'],
];

export default function CinematicScene({ children, selectedScenario, onSelectScenario, fleet, queue, npv, resultDigest }) {
  const root = useRef(null);
  const [active, setActive] = useState(false);
  const [shot, setShot] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false);
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!query) return undefined;
    const update = () => setReducedMotion(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!active || !playing || reducedMotion) return undefined;
    const timer = window.setInterval(() => setShot(current => (current + 1) % SHOTS.length), 15000);
    return () => window.clearInterval(timer);
  }, [active, playing, reducedMotion]);
  useEffect(() => {
    const sync = () => { if (!document.fullscreenElement && active) setActive(false); };
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, [active]);
  const enter = async () => {
    setShot(0); setPlaying(true); setActive(true);
    try { await root.current?.requestFullscreen?.(); } catch { /* Fixed overlay remains available. */ }
  };
  const leave = async () => {
    setActive(false);
    if (document.fullscreenElement === root.current) await document.exitFullscreen();
  };
  return <div ref={root} className={`cinematic-scene${active ? ' is-cinematic' : ''}`} aria-label="Презентационный режим">
    {!active && <button type="button" className="cinematic-launch" onClick={enter}>▶ Показать как презентацию</button>}
    {active && <div className="cinematic-overlay" aria-live="polite">
      <div><small>РОБОДОВОД · СОХРАНЁННЫЙ СЦЕНАРИЙ · {shot + 1}/{SHOTS.length}</small>
        <h3>{SHOTS[shot][0]}</h3><p>{SHOTS[shot][1]}</p>
        {shot === 2 && <p><strong>Парк: {fleet ?? '—'} роботов · максимум очереди: {queue ?? 'смотрите отчёт симуляции'}</strong></p>}
        {shot === 3 && <p><strong>NPV покупки: {npv}</strong><small>Коммерческие условия и пригодность на объекте не подтверждены.</small></p>}
        <small>Идентификатор сохранённого результата: {resultDigest || 'не указан'}</small>
      </div>
      <div className="cinematic-actions">
        {onSelectScenario && <button type="button" onClick={() => onSelectScenario(selectedScenario === 'base' ? 'peak' : 'base')}>A/B: {selectedScenario === 'base' ? '2 000 → 2 400' : '2 400 → 2 000'} паллет/сутки</button>}
        <button type="button" onClick={() => setShot(current => (current + SHOTS.length - 1) % SHOTS.length)} aria-label="Предыдущий кадр">←</button>
        <button type="button" onClick={() => setPlaying(current => !current)}>{playing ? 'Пауза кадров' : 'Продолжить кадры'}</button>
        <button type="button" onClick={() => setShot(current => (current + 1) % SHOTS.length)} aria-label="Следующий кадр">→</button>
        <button type="button" onClick={leave}>Закрыть показ</button>
      </div>
    </div>}
    {children}
  </div>;
}
