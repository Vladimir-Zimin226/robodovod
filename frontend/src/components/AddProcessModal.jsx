import { useState } from 'react';

const API = import.meta.env.VITE_API_URL || '';

const PROCESS_OPTIONS = [
  ['cleaning', 'Уборка'],
  ['delivery', 'Доставка'],
  ['palletizing', 'Паллетизация'],
  ['transport', 'Транспортировка'],
];

const CARGO_BY_PROCESS = {
  cleaning: 'pallets', delivery: 'deliveries',
  palletizing: 'cases', transport: 'pallets',
};

const FIELDS = {
  transport: [
    ['pallets_per_day', 'Объём в сутки', 'шт'],
    ['avg_distance_m', 'Среднее плечо', 'м'],
    ['aisle_width_m', 'Мин. проход', 'м'],
    ['payload_kg', 'Вес единицы', 'кг'],
  ],
  cleaning: [
    ['area_m2', 'Площадь уборки', 'м²'],
    ['aisle_width_m', 'Мин. проход', 'м'],
  ],
  delivery: [
    ['pallets_per_day', 'Доставок в сутки', 'шт'],
    ['avg_distance_m', 'Средняя дальность', 'м'],
    ['aisle_width_m', 'Мин. коридор', 'м'],
  ],
  palletizing: [
    ['pallets_per_day', 'Коробов в сутки', 'шт'],
    ['payload_kg', 'Вес короба', 'кг'],
  ],
};

export default function AddProcessModal({ objectType, sharedParams, onAdd, onClose }) {
  const [processType, setProcessType] = useState('cleaning');
  const [params, setParams] = useState({
    area_m2: sharedParams?.area_m2,
    avg_distance_m: sharedParams?.avg_distance_m || 100,
    aisle_width_m: sharedParams?.aisle_width_m || 2.5,
    pallets_per_day: null,
    payload_kg: 700,
    staff_headcount: null,
    fte_cost_rub: sharedParams?.fte_cost_rub,
    shifts_count: sharedParams?.shifts_count || 2,
    shift_hours: sharedParams?.shift_hours || 8,
    cleaning_frequency_per_day: 1,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const mandatory = processType === 'cleaning' ? 'area_m2' : 'pallets_per_day';
  const canCalc = params[mandatory] != null && params[mandatory] > 0;

  const set = (k, v) => setParams((p) => ({ ...p, [k]: v }));

  const calculate = async () => {
    setBusy(true);
    setError('');
    try {
      const inp = {
        object_type: objectType,
        process_type: processType,
        cargo_type: CARGO_BY_PROCESS[processType],
        area_m2: params.area_m2,
        avg_distance_m: params.avg_distance_m,
        pallets_per_day: params.pallets_per_day,
        shifts_count: params.shifts_count,
        shift_hours: params.shift_hours,
        staff_headcount: params.staff_headcount,
        fte_cost_rub: params.fte_cost_rub,
        aisle_width_m: params.aisle_width_m,
        payload_kg: params.payload_kg,
        cleaning_frequency_per_day: params.cleaning_frequency_per_day,
      };
      const res = await fetch(`${API}/api/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inp),
      });
      if (!res.ok) {
        const e = await res.json();
        setError(e.detail || 'Ошибка расчёта');
        return;
      }
      const result = await res.json();
      onAdd({ input: inp, result, label: PROCESS_OPTIONS.find(([v]) => v === processType)?.[1] });
    } catch {
      setError('Нет связи с сервером');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-[480px] max-h-[90vh] overflow-auto shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Добавить процесс</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">
            ✕
          </button>
        </div>

        <div className="mb-4">
          <label className="block text-xs text-slate-500 mb-1">Процесс</label>
          <div className="grid grid-cols-2 gap-2">
            {PROCESS_OPTIONS.map(([v, l]) => (
              <button
                key={v}
                onClick={() => setProcessType(v)}
                className={`rounded-lg py-2 text-sm ${
                  processType === v
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3 mb-4">
          {(FIELDS[processType] || []).map(([k, label, unit]) => (
            <label key={k} className="block text-xs text-slate-500">
              {label}{unit ? `, ${unit}` : ''}{' '}
              {mandatory === k && <span className="text-red-500">*</span>}
              <input
                type="number"
                value={params[k] ?? ''}
                onChange={(e) =>
                  set(k, e.target.value === '' ? null : +e.target.value)
                }
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </label>
          ))}
          {processType === 'cleaning' && (
            <label className="block text-xs text-slate-500">
              Уборок в день
              <div className="flex gap-1 mt-1">
                {[1, 2, 3].map((n) => (
                  <button
                    key={n}
                    onClick={() => set('cleaning_frequency_per_day', n)}
                    className={`flex-1 rounded-lg py-1.5 text-sm ${
                      params.cleaning_frequency_per_day === n
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </label>
          )}
          <label className="block text-xs text-slate-500">
            Смен
            <div className="flex gap-1 mt-1">
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  onClick={() => set('shifts_count', n)}
                  className={`flex-1 rounded-lg py-1.5 text-sm ${
                    params.shifts_count === n ? 'bg-blue-600 text-white' : 'bg-slate-100'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </label>
          <label className="block text-xs text-slate-500">
            Штат в процессе
            <input
              type="number"
              value={params.staff_headcount ?? ''}
              onChange={(e) =>
                set('staff_headcount', e.target.value === '' ? null : +e.target.value)
              }
              placeholder="не указан — оценка"
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-xs text-slate-500">
            Зарплата/мес, ₽
            <input
              type="number"
              value={params.fte_cost_rub ? Math.round(params.fte_cost_rub / 15.624) : ''}
              onChange={(e) =>
                set('fte_cost_rub', e.target.value ? Math.round(+e.target.value * 15.624) : null)
              }
              placeholder="80 000"
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </label>
        </div>

        {error && (
          <div className="text-xs text-red-500 bg-red-50 border border-red-200 rounded-lg p-2 mb-3">
            {error}
          </div>
        )}

        <button
          onClick={calculate}
          disabled={!canCalc || busy}
          className={`w-full rounded-xl py-3 text-sm font-semibold ${
            canCalc && !busy ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-400'
          }`}
        >
          {busy ? 'Расчёт…' : 'Рассчитать и добавить'}
        </button>
      </div>
    </div>
  );
}
