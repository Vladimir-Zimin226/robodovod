import FloorplanUploader from './FloorplanUploader';

// ─── Опции груза для транспортировки ───
const CARGO_OPTIONS_BASE = [
  {
    value: 'pallets',
    label: 'Паллеты',
    icon: '📦',
    unit: 'паллет',
    hint: 'Стандартная европаллета, обычно 300–1200 кг',
  },
  {
    value: 'boxes',
    label: 'Коробки',
    icon: '📫',
    unit: 'коробок',
    hint: 'Штучные грузы, мешки, кофры, обычно 5–50 кг',
  },
];

const CARTS_OPTION = {
  value: 'carts',
  label: 'Тележки',
  icon: '🛒',
  unit: 'тележко-рейсов',
  hint: 'Поезда багажных тележек',
};

function cargoOptionsFor(objectType) {
  if (objectType === 'airport') {
    return [CARTS_OPTION];
  }
  return CARGO_OPTIONS_BASE;
}

function findCargoOption(options, value) {
  return options.find((o) => o.value === value) || options[0];
}

// ─── Поля по процессам ───
const PROCESSES = [
  ['transport', 'Транспортировка'],
  ['palletizing', 'Паллетизация'],
  ['cleaning', 'Уборка'],
  ['delivery', 'Доставка'],
];

const PROCESS_KEYS_BY_OBJECT = {
  retail: new Set(['transport', 'palletizing']),
  airport: new Set(['transport', 'cleaning']),
  clinic: new Set(['delivery', 'cleaning']),
  other: new Set(['transport', 'palletizing', 'cleaning', 'delivery']),
};

const MANDATORY = {
  transport: 'pallets_per_day',
  palletizing: 'pallets_per_day',
  delivery: 'pallets_per_day',
  cleaning: 'area_m2',
};

const CARGO_FIXED = {
  palletizing: 'cases',
  cleaning: 'pallets',
  delivery: 'deliveries',
};

const DURATIONS = [6, 8, 10, 12];

const HORIZONS = [
  { v: 5, label: '5 лет', hint: 'Базовый: окупаемость в первые годы' },
  { v: 7, label: '7 лет', hint: 'Сбалансированный: полный цикл батарей' },
  { v: 10, label: '10 лет', hint: 'Долгосрочный: жизненный цикл парка' },
];

const PATTERN = {
  24: 'непрерывный режим',
  20: 'две смены по 10 ч',
  18: 'три смены по 6 ч',
  16: 'двухсменка',
  12: 'длинная смена',
  10: 'одна смена',
  8: 'одна смена',
  6: 'короткий день',
};

export default function ParamsPanel({
  collected,
  setManual,
  sources,
  objectType,
  onReady,
}) {
  const process = collected.process_type || 'transport';
  const isTransport = process === 'transport';
  const cargoOptions = cargoOptionsFor(objectType);
  const availableProcesses = PROCESSES.filter(([key]) =>
    (PROCESS_KEYS_BY_OBJECT[objectType] || PROCESS_KEYS_BY_OBJECT.other).has(key)
  );
  const cargoType =
    collected.cargo_type ||
    (isTransport ? cargoOptions[0].value : CARGO_FIXED[process] || 'pallets');
  const currentCargo = findCargoOption(cargoOptions, cargoType);
  const cargoUnit = currentCargo.unit;

  const mandatory = MANDATORY[process];
  const shifts = collected.shifts_count || 2;
  const duration = collected.shift_hours || 8;
  const opHours = shifts * duration;
  const invalid = opHours > 24;
  const horizon = collected.horizon_years || 5;
  const salaryMonth = collected.fte_cost_rub
    ? Math.round(collected.fte_cost_rub / 15.624)
    : '';
  const canCalc =
    !invalid && collected[mandatory] != null && collected[mandatory] !== '';
  const filled = collected[mandatory] != null && collected[mandatory] !== '';

  const shiftAllowed = (s) => s * duration <= 24;
  const durationAllowed = (d) => shifts * d <= 24;

  // ─── Ползунок высвобождения ───
  const staff = collected.staff_headcount;
  const sliderEnabled = staff != null && staff > 0;
  const requested = collected.released_headcount;
  const sliderValue = requested ?? (staff || 0);
  const isFull = requested == null || requested >= staff;

  const setReleased = (v) => {
    setManual('released_headcount', v === staff ? undefined : v);
  };

  // ─── Смена груза ───
  const setCargo = (value) => {
    setManual('cargo_type', value);
    setManual('payload_kg', undefined);
    setManual('units_per_trip', undefined);
  };

  const setProcess = (newProcess) => {
    setManual('process_type', newProcess);
    if (newProcess === 'transport') {
      const def = cargoOptions[0].value;
      setManual('cargo_type', def);
    } else {
      setManual('cargo_type', CARGO_FIXED[newProcess] || 'pallets');
    }
    setManual('units_per_trip', undefined);
  };

  const volumeLabel =
    process === 'cleaning'
      ? 'Площадь уборки'
      : process === 'palletizing'
        ? 'Коробов в сутки'
        : process === 'delivery'
          ? 'Доставок в сутки'
          : `${cargoUnit} в сутки`;

  const num = (k, label, unit, extra = {}) => (
    <label key={k} className="block text-xs text-slate-500">
      {label}
      {unit ? `, ${unit}` : ''}{' '}
      {mandatory === k && <span className="text-red-500">*</span>}
      <input
        type="number"
        value={collected[k] ?? ''}
        placeholder={extra.placeholder ? String(extra.placeholder) : '—'}
        onChange={(e) =>
          setManual(k, e.target.value === '' ? undefined : +e.target.value)
        }
        className={`w-full border rounded-lg px-2 py-1.5 text-sm ${
          sources[k] === 'ai'
            ? 'border-green-400'
            : sources[k] === 'manual'
              ? 'border-blue-400'
              : sources[k] === 'file'
                ? 'border-amber-400'
              : ''
        }`}
      />
    </label>
  );

  return (
    <aside className="w-96 border-l bg-white p-4 overflow-auto">
      <h3 className="font-semibold text-sm mb-3">Параметры объекта</h3>

      {/* ─── Загрузка плана ─── */}
      <div className="mb-4">
        <FloorplanUploader
          onResult={(data) => {
            setManual('area_m2', data.area_m2);
            setManual('avg_distance_m', data.avg_distance_m);
            setManual('facility_width_m', data.width_m);
            setManual('facility_depth_m', data.height_m);
            setManual('polygon', data.zoneMappings[0]?.polygon);
            setManual('_floorplan_image', data.imageData);
          }}
        />
      </div>

      {/* ─── Процесс ─── */}
      <label className="block text-xs text-slate-500 mb-3">
        Процесс
        <select
          value={process}
          onChange={(e) => setProcess(e.target.value)}
          className="w-full border rounded-lg px-2 py-1.5 text-sm"
        >
          {availableProcesses.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>

      {/* ─── Что перемещаем ─── */}
      {isTransport && (
        <div className="mb-3">
          <div className="text-xs text-slate-500 mb-1.5">Что перемещаем</div>
          <div
            className={`grid gap-1 ${
              cargoOptions.length === 3 ? 'grid-cols-3' : 'grid-cols-2'
            }`}
          >
            {cargoOptions.map((opt) => {
              const active = cargoType === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => setCargo(opt.value)}
                  className={`rounded-lg py-2 px-1 text-center transition ${
                    active
                      ? 'bg-blue-600 text-white shadow'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <div className="text-lg leading-none mb-1">{opt.icon}</div>
                  <div className="text-[11px] font-semibold">{opt.label}</div>
                </button>
              );
            })}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">
            {currentCargo.hint}
          </div>
        </div>
      )}

      {/* ─── Смены + длительность ─── */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <label className="text-xs text-slate-500">
          Смен в сутки
          <div className="flex gap-1 mt-0.5">
            {[1, 2, 3, 4].map((s) => (
              <button
                key={s}
                disabled={!shiftAllowed(s)}
                onClick={() => setManual('shifts_count', s)}
                className={`flex-1 rounded-lg py-1.5 text-sm ${
                  shifts === s
                    ? 'bg-blue-600 text-white'
                    : shiftAllowed(s)
                      ? 'bg-slate-100'
                      : 'bg-slate-50 text-slate-300'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </label>
        <label className="text-xs text-slate-500">
          Длительность
          <div className="flex gap-1 mt-0.5">
            {DURATIONS.map((d) => (
              <button
                key={d}
                disabled={!durationAllowed(d)}
                onClick={() => setManual('shift_hours', d)}
                className={`flex-1 rounded-lg py-1.5 text-sm ${
                  duration === d
                    ? 'bg-blue-600 text-white'
                    : durationAllowed(d)
                      ? 'bg-slate-100'
                      : 'bg-slate-50 text-slate-300'
                }`}
              >
                {d}ч
              </button>
            ))}
          </div>
        </label>
      </div>
      <div
        className={`text-[10px] mb-3 ${
          invalid ? 'text-red-500 font-semibold' : 'text-slate-400'
        }`}
      >
        {invalid
          ? `${shifts}×${duration} = ${opHours} ч > 24 ч — выберите другой режим`
          : `Объект работает: ${opHours} ч/сутки${
              PATTERN[opHours] ? ' · ' + PATTERN[opHours] : ''
            }`}
      </div>

      {/* ─── Горизонт ─── */}
      <div className="mb-3">
        <label className="text-xs text-slate-500">
          Горизонт расчёта
          <div className="flex gap-1 mt-0.5">
            {HORIZONS.map(({ v, label }) => (
              <button
                key={v}
                onClick={() => setManual('horizon_years', v)}
                className={`flex-1 rounded-lg py-1.5 text-sm ${
                  horizon === v ? 'bg-blue-600 text-white' : 'bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </label>
        <div className="text-[10px] text-slate-400 mt-1">
          {HORIZONS.find((h) => h.v === horizon)?.hint}
        </div>
      </div>

      {/* ─── Частота уборки ─── */}
      {process === 'cleaning' && (
        <label className="block text-xs text-slate-500 mb-3">
          Уборок в день
          <div className="flex gap-1 mt-0.5">
            {[1, 2, 3, 4].map((s) => (
              <button
                key={s}
                onClick={() => setManual('cleaning_frequency_per_day', s)}
                className={`flex-1 rounded-lg py-1 text-sm ${
                  (collected.cleaning_frequency_per_day || 1) === s
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </label>
      )}

      {/* ─── Основные поля ─── */}
      <div className="space-y-2 mb-4">
        {/* Объём */}
        {num('pallets_per_day', volumeLabel, 'шт')}

        {/* Плечо */}
        {(process === 'transport' || process === 'delivery') &&
          num('avg_distance_m', 'Среднее плечо', 'м')}

        {/* Площадь */}
        {(process === 'transport' || process === 'cleaning') &&
          num('area_m2', 'Площадь объекта', 'м²')}

        {/* Максимальный вес груза — ВАЖНО */}
        {process !== 'cleaning' && (
          <div className="block text-xs text-slate-500 border border-amber-200 bg-amber-50/40 rounded-lg p-2">
            <div className="flex justify-between items-center mb-1">
              <span className="font-semibold text-slate-700">
                Максимальный вес груза, кг
              </span>
              <span className="text-[9px] text-amber-600 uppercase tracking-wider">
                влияет на выбор робота
              </span>
            </div>
            <input
              type="number"
              value={collected.payload_kg ?? ''}
              placeholder="—"
              onChange={(e) =>
                setManual(
                  'payload_kg',
                  e.target.value === '' ? undefined : +e.target.value
                )
              }
              className={`w-full border rounded-lg px-2 py-1.5 text-sm ${
                sources.payload_kg === 'ai'
                  ? 'border-green-400'
                  : sources.payload_kg === 'manual'
                    ? 'border-blue-400'
                    : 'border-slate-300'
              }`}
            />
            <div className="text-[10px] text-slate-500 mt-1">
              {cargoType === 'boxes' &&
                'Коробки обычно 5–50 кг. Тяжёлые (>50 кг) — только паллетные роботы.'}
              {cargoType === 'pallets' &&
                'Паллеты обычно 300–1200 кг. Лёгкие (<250 кг) — подойдут малые AMR.'}
              {cargoType === 'carts' &&
                'Тележки обычно 0 кг (вес тянет сам робот)'}
              {cargoType === 'deliveries' && 'Доставки обычно 5–15 кг.'}
              {cargoType === 'cases' &&
                'Вес короба для паллетайзера: 5–25 кг (ограничение по захвату).'}
            </div>
          </div>
        )}

        {/* Штук за рейс — только для коробок */}
        {isTransport &&
          cargoType === 'boxes' &&
          num('units_per_trip', 'Штук за рейс', 'шт')}

        {/* Проход */}
        {(process === 'transport' ||
          process === 'cleaning' ||
          process === 'delivery') &&
          num('aisle_width_m', 'Мин. проход', 'м')}

        {/* Штат */}
        {num('staff_headcount', 'Текущий штат', 'чел')}

        {/* Ползунок высвобождения */}
        {sliderEnabled && (
          <div className="block text-xs text-slate-500 border border-slate-200 rounded-lg p-2 bg-slate-50">
            <div className="font-semibold text-slate-700 text-sm">
              Сколько сотрудников заменить роботами
            </div>
            <div className="text-[10px] text-slate-400 mb-1">
              Двигайте ползунок: роботы возьмут на себя часть работы
            </div>
            <div className="text-slate-600 mb-1">
              {isFull ? (
                <span className="text-slate-400">
                  Заменить всех, кого может робот
                </span>
              ) : requested === 0 ? (
                <span className="text-slate-400">Никого не заменяем</span>
              ) : (
                <span>
                  Хотите заменить <b>{requested}</b> из {staff} человек
                </span>
              )}
            </div>
            <input
              type="range"
              min={0}
              max={staff}
              step={1}
              value={sliderValue}
              onChange={(e) => setReleased(+e.target.value)}
              className="w-full"
            />
            <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
              <span>0</span>
              <span>все ({staff})</span>
            </div>
          </div>
        )}

        {/* Зарплата */}
        <label className="block text-xs text-slate-500">
          Зарплата/мес, ₽
          <input
            type="number"
            value={salaryMonth}
            placeholder="80 000"
            onChange={(e) =>
              setManual(
                'fte_cost_rub',
                e.target.value ? Math.round(+e.target.value * 15.624) : undefined
              )
            }
            className={`w-full border rounded-lg px-2 py-1.5 text-sm ${
              sources.fte_cost_rub === 'ai'
                ? 'border-green-400'
                : sources.fte_cost_rub === 'manual'
                  ? 'border-blue-400'
                  : ''
            }`}
          />
          {collected.fte_cost_rub && (
            <span className="text-[10px] text-slate-400">
              ≈ {(collected.fte_cost_rub / 1e6).toFixed(2)} млн ₽/год с налогами
            </span>
          )}
        </label>
      </div>

      {/* ─── Кнопка ─── */}
      <button
        disabled={!canCalc}
        onClick={onReady}
        className={`w-full rounded-xl py-3 text-sm font-semibold ${
          canCalc ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-400'
        }`}
      >
        РАССЧИТАТЬ ТЭО
      </button>
      <p className="text-[10px] text-slate-400 mt-2 text-center">
        {invalid
          ? 'Исправьте график работы'
          : filled
            ? 'Чем больше полей заполнено — тем точнее расчёт'
            : 'Заполните обязательное поле ( * )'}
      </p>
    </aside>
  );
}
