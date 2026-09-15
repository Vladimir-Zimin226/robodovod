import { useEffect, useRef, useState } from 'react';

const ZONE_COLORS = ['#3b82f6', '#8b5cf6', '#22c55e', '#f97316', '#06b6d4', '#ef4444'];

const STEPS = ['Файл', 'Масштаб', 'Зоны', 'Готово'];

function stepClass(i, current) {
  if (i === current) return 'px-2 py-0.5 rounded text-[9px] bg-blue-600 text-white';
  if (i < current) return 'px-2 py-0.5 rounded text-[9px] bg-green-600 text-white';
  return 'px-0 flex-1 text-center py-1 rounded text-[9px] bg-slate-100 text-slate-400';
}

export default function FloorplanUploader({ onResult, zoneOptions = [] }) {
  const [step, setStep] = useState(0);
  const [image, setImage] = useState(null);
  const [mPerPx, setMPerPx] = useState(null);
  const [scaleP1, setScaleP1] = useState(null);
  const [scaleP2, setScaleP2] = useState(null);
  const [scaleMeters, setScaleMeters] = useState('');
  const [zones, setZones] = useState([]);
  const [zoneAssignments, setZoneAssignments] = useState([]);
  const [currentZone, setCurrentZone] = useState([]);
  const [showUploader, setShowUploader] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(null);
  const canvasRef = useRef(null);
  const fileRef = useRef(null);
  const imgRef = useRef(null);

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        imgRef.current = img;
        setImage({ src: ev.target.result, width: img.width, height: img.height });
        setStep(1);
        setIsFullscreen(true);
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
  };

  const toImageCoords = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
    return { x: (cx - pan.x) / zoom, y: (cy - pan.y) / zoom };
  };

  const handleClick = (e) => {
    if (e.button !== 0 || isDragging) return;
    const pt = toImageCoords(e);
    if (!pt) return;

    if (step === 1) {
      if (!scaleP1) {
        setScaleP1(pt);
      } else if (!scaleP2) {
        setScaleP2(pt);
      }
    } else if (step === 2) {
      setCurrentZone(function(prev) {
        return prev.concat([pt]);
      });
    }
  };

  const handleMouseDown = (e) => {
    if (e.button === 2) {
      e.preventDefault();
      setIsDragging(true);
      setDragStart({ x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (!isDragging || !dragStart) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dx = (e.clientX - dragStart.x) * (canvas.width / rect.width);
    const dy = (e.clientY - dragStart.y) * (canvas.height / rect.height);
    setPan({ x: dragStart.panX + dx, y: dragStart.panY + dy });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragStart(null);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
    var factor = e.deltaY < 0 ? 1.2 : 0.83;
    var newZoom = Math.min(15, Math.max(0.3, zoom * factor));
    var scale = newZoom / zoom;
    setPan({
      x: cx - (cx - pan.x) * scale,
      y: cy - (cy - pan.y) * scale,
    });
    setZoom(newZoom);
  };

  const zoomBy = (f) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    var cx = canvas.width / 2;
    var cy = canvas.height / 2;
    var newZoom = Math.min(15, Math.max(0.3, zoom * f));
    var scale = newZoom / zoom;
    setPan({
      x: cx - (cx - pan.x) * scale,
      y: cy - (cy - pan.y) * scale,
    });
    setZoom(newZoom);
  };

  const calcScale = () => {
    if (!scaleP1 || !scaleP2 || !scaleMeters) return;
    var dist = Math.hypot(scaleP2.x - scaleP1.x, scaleP2.y - scaleP1.y);
    if (dist === 0) return;
    setMPerPx(parseFloat(scaleMeters) / dist);
    setStep(2);
  };

  const closeZone = () => {
    if (currentZone.length < 3) return;
    setZones(function(prev) {
      return prev.concat([currentZone]);
    });
    if (zoneOptions.length) setZoneAssignments((current) => [...current, zoneOptions.find(option => !current.includes(option.id))?.id || '']);
    setCurrentZone([]);
  };

  const finishAll = () => {
    if (zones.length === 0 && currentZone.length < 3) return;

    var allZones = zones.slice();
    if (currentZone.length >= 3) {
      allZones.push(currentZone);
    }
    const assignments = [...zoneAssignments];
    if (currentZone.length >= 3 && zoneOptions.length) assignments.push(zoneOptions.find(option => !assignments.includes(option.id))?.id || '');
    while (assignments.length < allZones.length) assignments.push('whole-object');
    if (zoneOptions.length && (assignments.some(id => !id) || new Set(assignments).size !== assignments.length)) return;

    var zonesM = allZones.map(function(z) {
      return z.map(function(p) {
        return { x: p.x * mPerPx, y: p.y * mPerPx };
      });
    });

    var totalArea = 0;
    zonesM.forEach(function(z) {
      var a = 0;
      for (var i = 0; i < z.length; i++) {
        var j = (i + 1) % z.length;
        a += z[i].x * z[j].y - z[j].x * z[i].y;
      }
      totalArea += Math.abs(a) / 2;
    });

    onResult({
      imageData: image.src,
      mPerPx: mPerPx,
      width_m: image.width * mPerPx,
      height_m: image.height * mPerPx,
      zones: zonesM,
      zoneMappings: zonesM.map((polygon, index) => ({ zone_id: assignments[index], polygon: polygon.map(point => [point.x, point.y]) })),
      area_m2: Math.round(totalArea),
    });
    setStep(3);
    setIsFullscreen(false);
  };

  const reset = () => {
    setStep(0);
    setImage(null);
    setScaleP1(null);
    setScaleP2(null);
    setScaleMeters('');
    setZones([]);
    setZoneAssignments([]);
    setCurrentZone([]);
    setMPerPx(null);
    imgRef.current = null;
    setShowUploader(false);
    setIsFullscreen(false);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  useEffect(function() {
    function onKey(e) {
      if (e.key === 'Escape' && isFullscreen) setIsFullscreen(false);
    }
    window.addEventListener('keydown', onKey);
    return function() {
      window.removeEventListener('keydown', onKey);
    };
  }, [isFullscreen]);

  useEffect(function() {
    var canvas = canvasRef.current;
    var img = imgRef.current;
    if (!canvas || !img || !image) return;
    if (step < 1 || step > 2) return;

    var ctx = canvas.getContext('2d');
    var size = { w: 700, h: 460 };
    if (isFullscreen) {
      size.w = Math.min(window.innerWidth - 100, 1800);
      size.h = Math.min(window.innerHeight - 220, 900);
    }

    var baseScale = Math.min(size.w / img.width, size.h / img.height);
    var cw = Math.round(img.width * baseScale);
    var ch = Math.round(img.height * baseScale);
    if (canvas.width !== cw) canvas.width = cw;
    if (canvas.height !== ch) canvas.height = ch;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = isFullscreen ? '#0f172a' : '#f1f5f9';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    var r = 5 / zoom;
    var lw = 2 / zoom;

    if (step === 1) {
      if (scaleP1 && !scaleP2) {
        ctx.fillStyle = '#3b82f6';
        ctx.beginPath();
        ctx.arc(scaleP1.x, scaleP1.y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      if (scaleP1 && scaleP2) {
        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = lw;
        ctx.beginPath();
        ctx.moveTo(scaleP1.x, scaleP1.y);
        ctx.lineTo(scaleP2.x, scaleP2.y);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(scaleP1.x, scaleP1.y, r, 0, Math.PI * 2);
        ctx.fillStyle = '#3b82f6';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(scaleP2.x, scaleP2.y, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (step === 2) {
      zones.forEach(function(zone, zi) {
        var color = ZONE_COLORS[zi % ZONE_COLORS.length];
        ctx.strokeStyle = color;
        ctx.lineWidth = lw;
        ctx.beginPath();
        zone.forEach(function(p, i) {
          if (i === 0) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        });
        ctx.closePath();
        ctx.stroke();
        ctx.fillStyle = color + '26';
        ctx.fill();
        zone.forEach(function(p) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 4 / zoom, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        });
      });

      if (currentZone.length > 0) {
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = lw;
        ctx.beginPath();
        currentZone.forEach(function(p, i) {
          if (i === 0) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        });
        ctx.stroke();
        currentZone.forEach(function(p) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 4 / zoom, 0, Math.PI * 2);
          ctx.fillStyle = '#f59e0b';
          ctx.fill();
        });
      }
    }

    ctx.restore();
  }, [step, image, scaleP1, scaleP2, zones, currentZone, zoom, pan, isFullscreen]);

  if (!showUploader) {
    return (
      <button
        onClick={function() { setShowUploader(true); }}
        className="w-full border-2 border-dashed border-slate-300 rounded-xl py-3 text-xs text-slate-500 hover:border-blue-400 hover:text-blue-600 transition"
      >
        📐 Загрузить план объекта
      </button>
    );
  }

  if (isFullscreen) {
    var hints = {
      1: 'Кликните две точки на известном расстоянии (например, между осями',
      2: 'Обведите каждое помещение (клик по углам, минимум 3). ПКМ = пан. Двойной клик = замкнуть.',
    };

    var canvasClass = 'border border-slate-700 rounded-lg cursor-crosshair';
    if (isDragging) {
      canvasClass = 'border border-slate-700 rounded-lg cursor-grabbing';
    }

    return (
      <div className="fixed inset-0 z-50 bg-slate-950 flex flex-col">
        <div className="bg-slate-900 px-4 py-2 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <h4 className="text-sm font-bold text-white">План объекта</h4>
            <div className="flex gap-1">
              {STEPS.map(function(s, i) {
                return (
                  <span key={s} className={stepClass(i, step)}>
                    {i < step ? '✓' : i + 1}
                  </span>
                );
              })}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-400">{'×' + zoom.toFixed(1)}</span>
            <button onClick={function() { zoomBy(1.3); }} className="w-8 h-8 rounded bg-slate-800 text-white font-bold text-sm">+</button>
            <button onClick={function() { zoomBy(0.77); }} className="w-8 h-8 rounded bg-slate-800 text-white font-bold text-sm">−</button>
            <button onClick={function() { setZoom(1); setPan({ x: 0, y: 0 }); }} className="w-8 h-8 rounded bg-slate-800 text-white text-[9px]">1:1</button>
            <button onClick={function() { setIsFullscreen(false); }} className="px-3 h-8 rounded bg-slate-700 text-white text-xs hover:bg-slate-600">Свернуть</button>
        </div>
        </div>

        <div className="bg-slate-900 px-4 py-2 border-b border-slate-800">
          <p className="text-xs text-slate-400">{hints[step]}</p>
        </div>

        <div className="flex-1 flex items-center justify-center overflow-hidden">
          <canvas
            ref={canvasRef}
            className={canvasClass}
            style={{ maxWidth: '100%', maxHeight: '100%', background: '#0f172a' }}
            onClick={handleClick}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onContextMenu={function(e) { e.preventDefault(); }}
            onDoubleClick={closeZone}
          />
        </div>

        <div className="bg-slate-900 px-4 py-3 border-t border-slate-800">
          {step === 1 && scaleP1 && scaleP2 && (
            <div className="flex gap-2 items-center max-w-md mx-auto">
              <input
                type="number"
                value={scaleMeters}
                onChange={function(e) { setScaleMeters(e.target.value); }}
                placeholder="метров между точками"
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500"
              />
              <button onClick={calcScale} disabled={!scaleMeters}
                className="bg-blue-600 text-white rounded-lg px-6 py-2 text-sm font-semibold disabled:bg-slate-700">OK</button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-2">
              {zoneOptions.length > 0 && zones.map((_, index) => (
                <label key={index} className="mx-auto flex max-w-md items-center gap-2 text-xs text-slate-300">
                  Полигон {index + 1}
                  <select value={zoneAssignments[index] || ''} onChange={(event) => setZoneAssignments((current) => { const next = current.map(value => value === event.target.value ? '' : value); next[index] = event.target.value; return next; })} className="flex-1 rounded bg-slate-800 px-2 py-1 text-white">
                    <option value="">Выберите зону</option>
                    {zoneOptions.map(zone => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
                  </select>
                </label>
              ))}
              <div className="flex gap-2 justify-center flex-wrap">
                <button onClick={function() { setCurrentZone([]); }} className="text-xs text-slate-400 underline">
                  отменить точки
                </button>
                <button onClick={closeZone} disabled={currentZone.length < 3}
                  className="bg-blue-600 text-white rounded-lg px-4 py-2 text-xs disabled:bg-slate-700">
                  Замкнуть зону ({currentZone.length})
                </button>
                {zones.length > 0 && (
                  <button onClick={function() { setZones(function(p) { return p.slice(0, -1); }); setZoneAssignments(function(p) { return p.slice(0, -1); }); }} className="text-xs text-red-400 underline">
                    удалить
                  </button>
                )}
              </div>
              <button
                onClick={finishAll}
                disabled={zones.length === 0 && currentZone.length < 3}
                className="w-full max-w-xs mx-auto bg-green-600 text-white rounded-lg px-6 py-2 text-sm font-semibold disabled:bg-slate-700"
              >
                Завершить и рассчитать ({zones.length} зон)
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="border-2 border-blue-200 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-blue-700">План объекта</h4>
        <div className="flex gap-2">
          {step >= 1 && step <= 2 && (
            <button onClick={function() { setIsFullscreen(true); }} className="text-xs text-blue-500 underline">↗</button>
          )}
          <button onClick={reset} className="text-xs text-slate-400 underline">сброс</button>
        </div>
      </div>

      {step === 0 && (
        <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center">
          <input ref={fileRef} type="file" accept="image/*" onChange={handleFile} className="hidden" />
          <button onClick={function() { fileRef.current.click(); }}
            className="bg-blue-600 text-white rounded-xl px-6 py-3 text-sm font-semibold">
            Выбрать файл
          </button>
          <p className="text-[10px] text-slate-400 mt-2">PNG, JPG. Не покидает браузер.</p>
        </div>
      )}

      {step >= 1 && step <= 2 && (
        <button onClick={function() { setIsFullscreen(true); }}
          className="w-full bg-slate-800 text-white rounded-lg py-2 text-xs font-semibold">
          ↗ Развернуть (для точности)
        </button>
      )}

      {step === 3 && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <p className="text-sm text-green-800 font-semibold">✓ План загружен</p>
          <p className="text-xs text-green-700 mt-1">Зон: {zones.length}</p>
        </div>
      )}
    </div>
  );
}
