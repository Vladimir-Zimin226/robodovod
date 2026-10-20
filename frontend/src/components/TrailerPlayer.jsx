import { useEffect, useRef, useState } from 'react';

const ROOT = '/demo/trailer';
const CHAPTERS = [
  'Склад · 3D', 'Склад · план 2D', 'Аэропорт · 3D',
  'Аэропорт · план 2D', 'Клиника · 3D', 'Клиника · план 2D',
];
const formatTime = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;

export default function TrailerPlayer() {
  const fullVideo = useRef(null);
  const previewVideo = useRef(null);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(180);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (reducedMotion) previewVideo.current?.pause();
    else previewVideo.current?.play().catch(() => {});
  }, [reducedMotion]);
  useEffect(() => {
    if (!open) return undefined;
    const escape = (event) => { if (event.key === 'Escape') {
      fullVideo.current?.pause(); setTime(0); setOpen(false);
    } };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [open]);
  const stop = () => { fullVideo.current?.pause(); if (fullVideo.current) fullVideo.current.currentTime = 0; setTime(0); };
  const close = () => { stop(); setOpen(false); };
  const toggle = () => {
    if (!fullVideo.current) return;
    if (fullVideo.current.paused) fullVideo.current.play().catch(() => {});
    else fullVideo.current.pause();
  };
  const seek = (seconds) => { if (fullVideo.current) fullVideo.current.currentTime = seconds; setTime(seconds); };
  return <section className="trailer-section" aria-label="Трейлер сцен">
    <div className="trailer-heading"><div><h2>Как выглядит оценка</h2>
      <p>Шесть кадров работающих сцен: склад, аэропорт и клиника в 3D и на плане. Геометрия демонстрационная.</p></div>
      <span>3 минуты · без музыки</span></div>
    {failed ? <div className="trailer-fallback"><h3>Галерея кадров</h3><p>Видео недоступно. Ниже — шесть статичных кадров из runtime сцен.</p>
      <div>{CHAPTERS.map((chapter, index) => <figure key={chapter}><img
        src={`${ROOT}/frames/chapter-${index + 1}.jpg`} alt={`${chapter}; демонстрационная сцена`} loading="lazy" />
        <figcaption>{chapter}</figcaption></figure>)}</div></div>
      : <div className="trailer-preview"><video ref={previewVideo} autoPlay={!reducedMotion} muted loop playsInline
        preload="metadata" poster={`${ROOT}/robodovod-trailer-poster.jpg`}
        onError={() => setFailed(true)} aria-label="Немое короткое видео сцен">
        <source src={`${ROOT}/robodovod-trailer-preview-720p.mp4`} type="video/mp4" /></video>
        <button type="button" onClick={() => setOpen(true)}>Смотреть полный трейлер</button>
        <span>Текущие 2D/3D сцены · полный ролик запускается по нажатию</span></div>}
    {open && !failed && <div className="trailer-dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) close();
    }}><div className="trailer-dialog" role="dialog" aria-modal="true" aria-label="Полный трейлер сцен">
      <div className="trailer-dialog-head"><strong>РОБОДОВОД · сцены и планы</strong><button type="button" onClick={close} aria-label="Закрыть трейлер">Закрыть</button></div>
      <video ref={fullVideo} autoPlay muted playsInline preload="metadata"
        poster={`${ROOT}/robodovod-trailer-poster.jpg`}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
        onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
        onError={() => { setFailed(true); close(); }} aria-label="Полный трейлер из шести сцен">
        <source src={`${ROOT}/robodovod-trailer-web-720p.mp4`} type="video/mp4" />
        <track kind="captions" src={`${ROOT}/robodovod-trailer.ru.vtt`} srcLang="ru" label="Русские субтитры" default />
      </video>
      <p aria-live="polite">{CHAPTERS[Math.min(5, Math.floor(time / 30))]} · демонстрационная сцена, не обмер объекта</p>
      <div className="trailer-controls"><button type="button" onClick={toggle}>{playing ? 'Пауза' : 'Воспроизвести'}</button>
        <button type="button" onClick={stop}>Стоп</button>
        <label>Перемотка <input type="range" min="0" max={duration || 180} step="0.1" value={time}
          onChange={(event) => seek(Number(event.target.value))} /></label>
        <span>{formatTime(time)} / {formatTime(duration)}</span></div>
      <nav aria-label="Главы трейлера">{CHAPTERS.map((chapter, index) =>
        <button type="button" key={chapter} onClick={() => seek(index * 30)}>{chapter}</button>)}</nav>
      <p className="trailer-credit">Кадры захвачены из локальных SceneModel/WebGL рендеров. Музыкальная дорожка отсутствует.</p>
    </div></div>}
  </section>;
}
