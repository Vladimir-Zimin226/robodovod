import { useState } from 'react';

const PROCESSES = [
  ['transport', 'Транспортировка', 'pallets'],
  ['palletizing', 'Паллетизация', 'cases'],
  ['cleaning', 'Уборка', 'pallets'],
  ['delivery', 'Доставка', 'deliveries'],
];

const PROCESS_KEYS_BY_OBJECT = {
  retail: new Set(['transport', 'palletizing']),
  airport: new Set(['transport', 'cleaning']),
  clinic: new Set(['delivery', 'cleaning']),
  other: new Set(['transport', 'palletizing', 'cleaning', 'delivery']),
};

const PROCESS_ICON = {
  transport: '🚚',
  palletizing: '🤖',
  cleaning: '🧹',
  delivery: '🛎',
};

const CARGO_OPTIONS_BASE = [
  { value: 'pallets', label: 'Паллеты', icon: '📦', unit: 'паллет' },
  { value: 'boxes', label: 'Коробки', icon: '📫', unit: 'коробок' },
];

const CARTS_OPTION = {
  value: 'carts',
  label: 'Тележки',
  icon: '🛒',
  unit: 'тележко-рейсов',
};

function cargoOptionsFor(objectType) {
  if (objectType === 'airport') {
    return [CARTS_OPTION];
  }
  return CARGO_OPTIONS_BASE;
}

const CARGO_FIXED = {
  palletizing: 'cases',
  cleaning: 'pallets',
  delivery: 'deliveries',
};

const emptyZone = (objectType) => {
  const opts = cargoOptionsFor(objectType);
  return {
    id: `Z${Date.now().toString(36).slice(-4)}`,
    name: '',
    process_type: 'transport',
    cargo_type: opts[0].value,
    area_m2: null,
    shifts_count: 2,
    shift_hours: 8,
    volume_per_day: null,
    staff_headcount: null,
    aisle_width_m: null,
    avg_distance_m: null,
    payload_kg: null,
    units_per_trip: null,
    released_headcount: null,
  };
};

export default function ZonalPanel({
  zones,
  setZones,
  shared,
  setShared,
  objectType,
  onReady,
}) {
  const [editingZone, setEditingZone] = useState(null);
  const cargoOptions = cargoOptionsFor(objectType);
  const availableProcesses = PROCESSES.filter(([key]) =>
    (PROCESS_KEYS_BY_OBJECT[objectType] || PROCESS_KEYS_BY_OBJECT.other).has(key)
  );

  const addZone = () => {
    const z = emptyZone(objectType);
    setZones((prev) => [...prev, z]);
    setEditingZone(z.id);
  };

  const updateZone = (id, patch) => {
    setZones((prev) => prev.map((z) => (z.id === id ? { ...z, ...patch } : z)));
  };

  const removeZone = (id) => {
    setZones((prev) => prev.filter((z) => z.id !== id));
    if (editingZone === id) setEditingZone(null);
  };

  const setProcess = (id, newProcess) => {
    const patch = { process_type: newProcess };
    if (newProcess === 'transport') {
      patch.cargo_type = cargoOptions[0].value;
    } else {
      patch.cargo_type = CARGO_FIXED[newProcess] || 'pallets';
    }
    patch.units_per_trip = null;
    updateZone(id, patch);
  };

  const setCargo = (id, value) => {
    updateZone(id, {
      cargo_type: value,
      payload_kg: null,
      units_per_trip: null,
    });
  };

  const canCalc =
    zones.length > 0 &&
    zones.every((z) =>
      z.process_type === 'cleaning' ? z.area_m2 > 0 : z.volume_per_day > 0
    );

  return (
    <aside className="w-[420px] border-l bg-white p-4 overflow-auto flex flex-col">
      <h3 className="font-semibold text-sm mb-3">Зоны склада</h3>

      <div className="mb-3">
        <FloorplanUploader
          zoneOptions={zones.map(zone => ({ id: zone.id, name: zone.name }))}
          onResult={(data) => {
            setShared('facility_width_m', data.width_m);
            setShared('facility_depth_m', data.height_m);
            setShared('_floorplan_image', data.imageData);
            const polygons = new Map(data.zoneMappings.map(item => [item.zone_id, item.polygon]));
            setZones(current => current.map(zone => ({ ...zone, polygon: polygons.get(zone.id) || null })));
          }}
        />
      </div>

      {/* ─── Общие параметры ─── */}
      <div className="bg-slate-50 rounded-lg p-3 mb-3">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">
          Общие для всех зон
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-slate-500">
            Зарплата/мес, ₽
            <input
              type="number"
              value={
                shared.fte_cost_rub
                  ? Math.round(shared.fte_cost_rub / 15.624)
                  : ''
              }
              placeholder="80 000"
              onChange={(e) =>
                setShared(
                  'fte_cost_rub',
                  e.target.value
                    ? Math.round(+e.target.value * 15.624)
                    : undefined
                )
              }
              className="w-full border rounded px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-slate-500">
            Дней в году
            <input
              type="number"
              value={shared.operating_days ?? ''}
              placeholder="365"
              onChange={(e) =>
                setShared(
                  'operating_days',
                  e.target.value ? +e.target.value : undefined
                )
              }
              className="w-full border rounded px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-slate-500 col-span-2">
            Горизонт расчёта
            <div className="flex gap-1 mt-0.5">
              {[5, 7, 10].map((h) => (
                <button
                  key={h}
                  onClick={() => setShared('horizon_years', h)}
                  className={`flex-1 rounded py-1 text-xs ${
                    (shared.horizon_years || 5) === h
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100'
                  }`}
                >
                  {h} лет
                </button>
              ))}
            </div>
          </label>
        </div>
      </div>

      {/* ─── Список зон ─── */}
      <div className="space-y-2 flex-1">
        {zones.length === 0 && (
          <div className="text-xs text-slate-400 text-center py-8 border-2 border-dashed rounded-xl">
            Добавьте первую зону — например, «Приёмка», «Хранение», «Отгрузка»
          </div>
        )}

        {zones.map((z, idx) => {
          const isOpen = editingZone === z.id;
          const hasMandatory =
            z.process_type === 'cleaning' ? z.area_m2 > 0 : z.volume_per_day > 0;
          const cargoOpt = cargoOptions.find((o) => o.value === z.cargo_type);
          const cargoUnit = cargoOpt?.unit || 'единиц';
          const isTransport = z.process_type === 'transport';
          const volumeLabel =
            z.process_type === 'cleaning'
              ? 'Площадь, м²'
              : z.process_type === 'palletizing'
                ? 'Коробов в сутки'
                : z.process_type === 'delivery'
                  ? 'Доставок в сутки'
                  : `${cargoUnit} в сутки`;

          return (
            <div
              key={z.id}
              className={`border rounded-lg overflow-hidden transition ${
                isOpen ? 'border-blue-400 shadow-sm' : ''
              }`}
            >
              <button
                onClick={() => setEditingZone(isOpen ? null : z.id)}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 text-left"
              >
                <span className="text-lg">{PROCESS_ICON[z.process_type]}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">
                    {z.name || `Зона ${idx + 1}`}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {z.process_type} · {z.shifts_count} см × {z.shift_hours} ч
                    {z.volume_per_day && ` · ${z.volume_per_day}/сутки`}
                    {z.area_m2 && ` · ${z.area_m2} м²`}
                  </div>
                </div>
                {hasMandatory ? (
                  <span className="text-green-500 text-xs">✓</span>
                ) : (
                  <span className="text-amber-500 text-xs">!</span>
                )}
                <span className="text-slate-400 text-xs">
                  {isOpen ? '▼' : '▶'}
                </span>
              </button>

              {isOpen && (
                <div className="border-t bg-slate-50 px-3 py-3 space-y-2">
                  <label className="block text-xs text-slate-500">
                    Название
                    <input
                      value={z.name}
                      onChange={(e) => updateZone(z.id, { name: e.target.value })}
                      placeholder="Приёмка"
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                  </label>

                  <label className="block text-xs text-slate-500">
                    Процесс
                    <div className="grid grid-cols-2 gap-1 mt-0.5">
                      {availableProcesses.map(([v, l]) => (
                        <button
                          key={v}
                          onClick={() => setProcess(z.id, v)}
                          className={`rounded py-1 text-xs ${
                            z.process_type === v
                              ? 'bg-blue-600 text-white'
                              : 'bg-white border'
                          }`}
                        >
                          {PROCESS_ICON[v]} {l}
                        </button>
                      ))}
                    </div>
                  </label>

                  {isTransport && (
                    <div className="block text-xs text-slate-500">
                      <div className="mb-1">Что перемещаем</div>
                      <div
                        className={`grid gap-1 ${
                          cargoOptions.length === 3
                            ? 'grid-cols-3'
                            : 'grid-cols-2'
                        }`}
                      >
                        {cargoOptions.map((opt) => {
                          const active = z.cargo_type === opt.value;
                          return (
                            <button
                              key={opt.value}
                              onClick={() => setCargo(z.id, opt.value)}
                              className={`rounded py-1.5 text-center text-xs transition ${
                                active
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-white border'
                              }`}
                            >
                              <span className="mr-1">{opt.icon}</span>
                              {opt.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-xs text-slate-500 col-span-2">
                      {volumeLabel} *
                      <input
                        type="number"
                        value={
                          z.process_type === 'cleaning'
                            ? z.area_m2 ?? ''
                            : z.volume_per_day ?? ''
                        }
                        onChange={(e) =>
                          updateZone(z.id, {
                            [z.process_type === 'cleaning'
                              ? 'area_m2'
                              : 'volume_per_day']:
                              e.target.value ? +e.target.value : null,
                          })
                        }
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </label>

                    {(isTransport || z.process_type === 'delivery') && (
                      <label className="text-xs text-slate-500">
                        Плечо, м
                        <input
                          type="number"
                          value={z.avg_distance_m ?? ''}
                          onChange={(e) =>
                            updateZone(z.id, {
                              avg_distance_m: e.target.value
                                ? +e.target.value
                                : null,
                            })
                          }
                          className="w-full border rounded px-2 py-1 text-sm"
                        />
                      </label>
                    )}

                    <label className="text-xs text-slate-500">
                      Проход, м
                      <input
                        type="number"
                        value={z.aisle_width_m ?? ''}
                        onChange={(e) =>
                          updateZone(z.id, {
                            aisle_width_m: e.target.value
                              ? +e.target.value
                              : null,
                          })
                        }
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </label>

                    {z.process_type !== 'cleaning' && (
                      <label className="text-xs text-slate-500 col-span-2 border border-amber-200 bg-amber-50/40 rounded px-2 py-1">
                        <div className="flex justify-between items-center">
                          <span className="font-semibold text-slate-700">
                            Макс. вес груза, кг
                          </span>
                          <span className="text-[9px] text-amber-600 uppercase tracking-wider">
                            влияет на выбор робота
                          </span>
                        </div>
                        <input
                          type="number"
                          value={z.payload_kg ?? ''}
                          placeholder="—"
                          onChange={(e) =>
                            updateZone(z.id, {
                              payload_kg: e.target.value
                                ? +e.target.value
                                : null,
                            })
                          }
                          className="w-full border rounded px-2 py-1 text-sm mt-1"
                        />
                      </label>
                    )}

                    {isTransport && z.cargo_type === 'boxes' && (
                      <label className="text-xs text-slate-500 col-span-2">
                        Штук за рейс
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={z.units_per_trip ?? ''}
                          placeholder="—"
                          onChange={(e) =>
                            updateZone(z.id, {
                              units_per_trip: e.target.value
                                ? +e.target.value
                                : null,
                            })
                          }
                          className="w-full border rounded px-2 py-1 text-sm"
                        />
                      </label>
                    )}

                    <label className="text-xs text-slate-500">
                      Смен
                      <input
                        type="number"
                        min={1}
                        max={4}
                        value={z.shifts_count ?? 2}
                        onChange={(e) =>
                          updateZone(z.id, { shifts_count: +e.target.value })
                        }
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </label>

                    <label className="text-xs text-slate-500">
                      Часов/смена
                      <input
                        type="number"
                        min={6}
                        max={12}
                        value={z.shift_hours ?? 8}
                        onChange={(e) =>
                          updateZone(z.id, { shift_hours: +e.target.value })
                        }
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </label>

                    <label className="text-xs text-slate-500 col-span-2">
                      Штат в зоне, чел
                      <input
                        type="number"
                        value={z.staff_headcount ?? ''}
                        onChange={(e) =>
                          updateZone(z.id, {
                            staff_headcount: e.target.value
                              ? +e.target.value
                              : null,
                          })
                        }
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </label>
                  </div>

                  <button
                    onClick={() => removeZone(z.id)}
                    className="text-[11px] text-red-500 underline"
                  >
                    Удалить зону
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <button
        onClick={addZone}
        className="w-full border-2 border-dashed border-slate-300 rounded-xl py-2 text-sm text-slate-500 hover:border-blue-400 hover:text-blue-600 transition mt-3"
      >
        ➕ Добавить зону
      </button>

      <button
        disabled={!canCalc}
        onClick={onReady}
        className={`w-full rounded-xl py-3 text-sm font-semibold mt-2 ${
          canCalc ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-400'
        }`}
      >
        РАССЧИТАТЬ ПО ЗОНАМ
      </button>
    </aside>
  );
}
import FloorplanUploader from './FloorplanUploader';
