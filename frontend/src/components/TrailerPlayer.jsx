import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

const ROOT = '/demo/trailer';
const CHAPTERS = ['Склад · 3D', 'Склад · 2D', 'Аэропорт · 3D', 'Аэропорт · 2D', 'Клиника · 3D', 'Клиника · 2D'];
const CHAPTER_SECONDS = 10;
const formatTime = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;

export default function TrailerPlayer() {
  const fullVideo = useRef(null);
  const previewVideo = useRef(null);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(0.8);
  const [captions, setCaptions] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(60);
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
  const openTrailer = () => {
    flushSync(() => setOpen(true));
    const video = fullVideo.current;
    if (!video) return;
    video.muted = false;
    video.volume = volume;
    video.play().catch(() => setPlaying(false));
  };
  const toggle = () => {
    if (!fullVideo.current) return;
    if (fullVideo.current.paused) fullVideo.current.play().catch(() => {});
    else fullVideo.current.pause();
  };
  const seek = (seconds) => { if (fullVideo.current) fullVideo.current.currentTime = seconds; setTime(seconds); };
  const toggleCaptions = () => {
    const track = fullVideo.current?.textTracks?.[0];
    if (!track) return;
    // TextTrack.mode is the browser's imperative caption control.
    // eslint-disable-next-line react-hooks/immutability
    track.mode = captions ? 'disabled' : 'showing';
    setCaptions(!captions);
  };
  return <section className="trailer-section" aria-label="Трейлер сцен">
    <div className="trailer-heading"><div><h2>Как выглядит оценка</h2>
      <p>Движение робота на складе, в аэропорту и клинике. Интерактивные 3D и 2D сцены.</p></div>
      <span>60 секунд · с музыкой</span></div>
    {failed ? <div className="trailer-fallback"><h3>Галерея кадров</h3><p>Видео недоступно. Ниже — кадры из runtime сцен.</p>
      <div>{CHAPTERS.map((chapter, index) => <figure key={chapter}><img
        src={`${ROOT}/frames/chapter-${index + 1}.jpg`} alt={`${chapter}; демонстрационная сцена`} loading="lazy" />
        <figcaption>{chapter}</figcaption></figure>)}</div></div>
      : <div className="trailer-preview"><video ref={previewVideo} autoPlay={!reducedMotion} muted loop playsInline
        preload="metadata" poster={`${ROOT}/robodovod-trailer-poster.jpg`}
        onError={() => setFailed(true)} aria-label="Немое короткое видео сцен">
        <source src={`${ROOT}/robodovod-trailer-preview-720p.mp4`} type="video/mp4" /></video>
        <button type="button" onClick={openTrailer}>Открыть полный трейлер</button>
        <span>Короткий немой предпросмотр · полный трейлер открывается по нажатию</span></div>}
    {open && !failed && <div className="trailer-dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) close();
    }}><div className="trailer-dialog" role="dialog" aria-modal="true" aria-label="Полный трейлер сцен">
      <div className="trailer-dialog-head"><strong>РОБОДОВОД · сцены и планы</strong><button type="button" onClick={close} aria-label="Закрыть трейлер">Закрыть</button></div>
      <video ref={fullVideo} playsInline preload="metadata"
        poster={`${ROOT}/robodovod-trailer-poster.jpg`}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
        onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
        onError={() => { setFailed(true); close(); }} aria-label="Полный трейлер: склад, аэропорт и клиника в 3D и 2D">
        <source src={`${ROOT}/robodovod-trailer-web-720p.mp4`} type="video/mp4" />
        <track kind="captions" src={`${ROOT}/robodovod-trailer.ru.vtt`} srcLang="ru" label="Русские субтитры" />
      </video>
      <p aria-live="polite">{CHAPTERS[Math.min(CHAPTERS.length - 1, Math.floor(time / CHAPTER_SECONDS))]} · демонстрационная сцена, не обмер объекта</p>
      <div className="trailer-controls"><button type="button" onClick={toggle}>{playing ? 'Пауза' : 'Воспроизвести'}</button>
        <button type="button" onClick={stop}>Стоп</button>
        <button type="button" onClick={() => { const next = !muted; fullVideo.current.muted = next; setMuted(next); }}
          aria-pressed={muted}>{muted ? 'Включить звук' : 'Выключить звук'}</button>
        <label>Громкость <input type="range" min="0" max="1" step="0.05" value={volume}
          aria-label="Громкость трейлера" onChange={(event) => {
            const next = Number(event.target.value);
            if (fullVideo.current) fullVideo.current.volume = next;
            setVolume(next);
          }} /></label>
        <button type="button" onClick={toggleCaptions} aria-pressed={captions}>{captions ? 'Скрыть субтитры' : 'Субтитры'}</button>
        <label>Перемотка <input type="range" min="0" max={duration || 60} step="0.1" value={time}
          onChange={(event) => seek(Number(event.target.value))} /></label>
        <span>{formatTime(time)} / {formatTime(duration)}</span></div>
      <nav aria-label="Главы трейлера">{CHAPTERS.map((chapter, index) =>
        <button type="button" key={chapter} onClick={() => seek(index * CHAPTER_SECONDS)}>{chapter}</button>)}</nav>
      <p className="trailer-credit">Кадры захвачены из локальных SceneModel/WebGL рендеров с маршрутом FastAPI. Музыка: предоставленная заказчиком композиция «Dead morose WMD 2». Трейлер демонстрирует движение; каталожная модель и экономика проверяются отдельно.</p>
    </div></div>}
  </section>;
}
