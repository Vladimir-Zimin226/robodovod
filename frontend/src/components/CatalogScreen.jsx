import { useEffect, useState } from 'react';

const API = import.meta.env.VITE_API_URL || '';

// ─── Категории с метаданными ───
const CATEGORIES = [
  {
    key: 'internal_mobile',
    label: 'Мобильные транспортные роботы',
    icon: '🚚',
    subtitle: 'Автономные тележки и тягачи для перемещения грузов',
    color: 'blue',
    metrics: [
      ['payload_kg', 'Грузоподъёмность', 'кг', '⚖️'],
      ['max_speed_m_s', 'Скорость', 'м/с', '💨'],
      ['autonomy_hours', 'Автономность', 'ч', '🔋'],
      ['min_aisle_width_m', 'Мин. проход', 'м', '↔️'],
    ],
  },
  {
    key: 'service_delivery',
    label: 'Роботы доставки',
    icon: '🛎',
    subtitle: 'Курьеры для доставки небольших грузов между точками',
    color: 'violet',
    metrics: [
      ['payload_kg', 'Грузоподъёмность', 'кг', '⚖️'],
      ['max_speed_m_s', 'Скорость', 'м/с', '💨'],
      ['autonomy_hours', 'Автономность', 'ч', '🔋'],
      ['min_aisle_width_m', 'Мин. коридор', 'м', '↔️'],
    ],
  },
  {
    key: 'cleaning_robot',
    label: 'Уборочные роботы',
    icon: '🧹',
    subtitle: 'Автономные поломоечные и подметальные машины',
    color: 'emerald',
    metrics: [
      ['cleaning_rate_m2_h', 'Скорость уборки', 'м²/ч', '📐'],
      ['autonomy_hours', 'Автономность', 'ч', '🔋'],
      ['min_aisle_width_m', 'Мин. проход', 'м', '↔️'],
      ['max_speed_m_s', 'Скорость', 'м/с', '💨'],
    ],
  },
  {
    key: 'fixed_cell',
    label: 'Стационарные ячейки',
    icon: '🤖',
    subtitle: 'Роботизированные ячейки для укладки коробов на паллеты',
    color: 'amber',
    metrics: [
      ['payload_kg', 'Грузоподъёмность', 'кг', '⚖️'],
      ['picks_per_min_max', 'Захваты/мин', 'раз/мин', '🤏'],
    ],
  },
  {
    key: 'aerial',
    label: 'Летательные системы',
    icon: '🛩',
    subtitle: 'Дроны для инвентаризации, инспекции и мониторинга',
    color: 'purple',
    badge: 'Отдельная ветка продукта',
    metrics: [
      ['flight_time_min', 'Время полёта', 'мин', '⏱'],
      ['scan_rate_m2_h', 'Сканирование', 'м²/ч', '📐'],
      ['max_scan_height_m', 'Высота', 'м', '📏'],
      ['position_accuracy_cm', 'Точность', 'см', '🎯'],
    ],
  },
];

// ─── Иконки роботов по id ───
const ROBOT_ICONS = {
  agv_pallet_qr: '📦',
  amr_light_250: '🛒',
  amr_heavy_1350: '🚛',
  agv_tug_k05: '🚂',
  courier_flashbot: '🚀',
  bella_bot: '🛎',
  cleaner_cc1_pro: '🧽',
  sweeper_mt1: '🧹',
  palletizer_cell_21: '🤖',
  drone_inventory: '🛩',
  drone_inventory_pro: '🛰',
  drone_inspection: '📡',
  drone_yard: '🚁',
};

const COLOR_CLASSES = {
  blue: { bg: 'from-blue-50 to-blue-100', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700', btn: 'bg-blue-600 hover:bg-blue-700' },
  violet: { bg: 'from-violet-50 to-violet-100', border: 'border-violet-200', badge: 'bg-violet-100 text-violet-700', btn: 'bg-violet-600 hover:bg-violet-700' },
  emerald: { bg: 'from-emerald-50 to-emerald-100', border: 'border-emerald-200', badge: 'bg-emerald-100 text-emerald-700', btn: 'bg-emerald-600 hover:bg-emerald-700' },
  amber: { bg: 'from-amber-50 to-amber-100', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-700', btn: 'bg-amber-600 hover:bg-amber-700' },
  purple: { bg: 'from-purple-50 to-blue-50', border: 'border-purple-200', badge: 'bg-purple-100 text-purple-700', btn: 'bg-purple-600 hover:bg-purple-700' },
};

export default function CatalogScreen({ objectType, onContinue }) {
  const [robots, setRobots] = useState([]);
  const [selected, setSelected] = useState([]);   // для сравнения
  const [showCompare, setShowCompare] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/robots`)
      .then((r) => r.json())
      .then(setRobots)
      .catch(() => {});
  }, []);

  const visible = robots.filter((r) =>
    (r.object_types || ['retail', 'other']).includes(objectType)
  );

  const toggle = (id) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const compareRobots = visible.filter((r) => selected.includes(r.id));

  const fmtPrice = (r) => {
    if (r.price?.basis === 'quote_required') return 'по запросу';
    const p = r.economics?.robot_capex_rub;
    return p ? `${(p / 1e6).toFixed(1)} млн ₽` : '—';
  };

  const OBJ_LABEL = {
    retail: 'Торговля / Склад',
    airport: 'Логистика / Аэропорт',
    clinic: 'Соц. сфера / Медучреждение',
    other: 'Произвольный объект',
  }[objectType] || 'Объект';

  // Считаем, сколько роботов реально видно
  const totalVisible = visible.length;

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-bold">Доступные решения</h1>
          <p className="text-slate-500 text-sm mt-1">
            {totalVisible} роботов · для объекта: <b>{OBJ_LABEL}</b>
          </p>
        </header>

        {/* ─── Секции по категориям ─── */}
        {CATEGORIES.map((cat) => {
          const items = visible.filter((r) => r.category === cat.key);
          if (items.length === 0) return null;
          const colors = COLOR_CLASSES[cat.color];

          return (
            <section key={cat.key} className="mb-8">
              <div className="flex items-baseline gap-3 mb-1">
                <span className="text-2xl">{cat.icon}</span>
                <h2 className="text-lg font-bold text-slate-800">{cat.label}</h2>
                <span className="text-xs text-slate-400">({items.length})</span>
                {cat.badge && (
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${colors.badge}`}>
                    {cat.badge}
                  </span>
                )}
              </div>
              <p className="text-slate-500 text-xs mb-4 ml-9">{cat.subtitle}</p>

              <div className="grid grid-cols-2 gap-4">
                {items.map((robot) => (
                  <RobotCard
                    key={robot.id}
                    robot={robot}
                    category={cat}
                    colors={colors}
                    isSelected={selected.includes(robot.id)}
                    onToggle={() => toggle(robot.id)}
                    fmtPrice={fmtPrice}
                  />
                ))}
              </div>
            </section>
          );
        })}

        {/* ─── Сравнение ─── */}
        {selected.length >= 2 && (
          <button
            onClick={() => setShowCompare(true)}
            className="mt-2 bg-slate-700 text-white rounded-xl px-4 py-2 text-sm"
          >
            Сравнить выбранные ({compareRobots.length})
          </button>
        )}

        {showCompare && compareRobots.length >= 2 && (
          <CompareTable
            robots={compareRobots}
            fmtPrice={fmtPrice}
            onClose={() => setShowCompare(false)}
          />
        )}

        {/* ─── CTA ─── */}
        <div className="mt-8 flex items-center justify-between">
          <p className="text-xs text-slate-400">
            Отметьте 2–3 решения для сравнения характеристик
          </p>
          <button
            onClick={onContinue}
            className="bg-blue-600 text-white rounded-xl px-6 py-3 text-sm font-semibold hover:bg-blue-700"
          >
            Далее: рассчитать ТЭО для моего процесса →
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Карточка робота — единая для всех категорий
// ═══════════════════════════════════════════════════════════════
function RobotCard({ robot, category, colors, isSelected, onToggle, fmtPrice }) {
  const icon = ROBOT_ICONS[robot.id] || category.icon;
  const purposes = robot.purpose || [];
  const specs = robot.specs || {};
  const purposesCount = purposes.length;

  // Собираем метрики: только те, у которых есть значения
  const metrics = category.metrics
    .map(([key, label, unit, ic]) => {
      const val = specs[key];
      if (val == null || val === 0) return null;
      return { key, label, unit, ic, val };
    })
    .filter(Boolean);

  return (
    <div
      className={`bg-white rounded-2xl border-2 transition overflow-hidden flex flex-col ${
        isSelected
          ? 'border-blue-400 shadow-md'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
      }`}
    >
      {/* Шапка */}
      <div className={`bg-gradient-to-br ${colors.bg} px-5 py-4 flex items-start gap-4`}>
        <div className="text-4xl select-none">{icon}</div>
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-slate-800 leading-tight">{robot.name}</h3>
          <div className="text-[11px] text-slate-500 mt-0.5 truncate">
            {robot.type_label || category.label}
            {specs.navigation_type && ` · ${specs.navigation_type}`}
          </div>
        </div>
        {/* Чекбокс сравнения */}
        <button
          onClick={onToggle}
          title={isSelected ? 'Убрать из сравнения' : 'Добавить к сравнению'}
          className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs transition flex-shrink-0 ${
            isSelected
              ? 'bg-blue-600 border-blue-600 text-white'
              : 'bg-white border-slate-300 text-slate-300 hover:border-slate-400'
          }`}
        >
          {isSelected ? '✓' : '+'}
        </button>
      </div>

      {/* Описание */}
      <div className="px-5 pt-3">
        <p className="text-xs text-slate-600 leading-relaxed">
          {robot.description}
        </p>
      </div>

      {/* Назначение */}
      {purposesCount > 0 && (
        <div className="px-5 pt-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">
            Назначение
          </div>
          <div className="flex flex-wrap gap-1.5">
            {purposes.map((p, i) => (
              <span
                key={i}
                className={`text-[10px] px-2 py-0.5 rounded-full border ${colors.badge} border-transparent`}
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Характеристики */}
      {metrics.length > 0 && (
        <div className="px-5 pt-4 flex-1">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">
            Характеристики
          </div>
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: `repeat(${Math.min(metrics.length, 4)}, minmax(0, 1fr))` }}
          >
            {metrics.slice(0, 4).map((m) => (
              <div key={m.key} className="bg-slate-50 rounded-lg p-2 text-center">
                <div className="text-sm leading-none mb-0.5">{m.ic}</div>
                <div className="text-sm font-bold text-slate-700 leading-tight">
                  {m.val}
                </div>
                <div className="text-[9px] text-slate-400">{m.unit}</div>
                <div className="text-[9px] text-slate-400 leading-tight mt-0.5">
                  {m.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Доп. инфа (мелким шрифтом) */}
      <div className="px-5 pt-3 pb-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500">
        {specs.operating_temp_c && (
          <span>🌡 <b className="text-slate-700">{specs.operating_temp_c}</b> °C</span>
        )}
        {specs.sensor_type && (
          <span>📷 <b className="text-slate-700">{specs.sensor_type}</b></span>
        )}
        {specs.requires_elevator === true && (
          <span className="text-amber-600">🛗 Требуется интеграция с лифтами</span>
        )}
        {specs.navigation_type && category.key === 'internal_mobile' && (
          <span>🧭 <b className="text-slate-700">{specs.navigation_type}</b></span>
        )}
      </div>

      {/* Подвал с ценой */}
      <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between bg-slate-50">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-slate-800">{fmtPrice(robot)}</div>
          <div className="text-[9px] text-slate-400 leading-tight truncate">
            {robot.price?.note || 'Цена по запросу'}
          </div>
        </div>
        <button
          onClick={onToggle}
          className={`text-[11px] rounded-lg px-3 py-1.5 font-semibold text-white transition flex-shrink-0 ${
            isSelected ? 'bg-slate-600 hover:bg-slate-700' : colors.btn
          }`}
        >
          {isSelected ? '✓ В сравнении' : 'Сравнить'}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Таблица сравнения — расширенная, с учётом категории
// ═══════════════════════════════════════════════════════════════
function CompareTable({ robots, fmtPrice, onClose }) {
  // Собираем union всех ключей specs, которые есть у кого-то из сравнимых
  const fieldsToShow = [
    ['payload_kg', 'Грузоподъёмность', 'кг'],
    ['max_speed_m_s', 'Скорость', 'м/с'],
    ['autonomy_hours', 'Автономность', 'ч'],
    ['min_aisle_width_m', 'Мин. проход', 'м'],
    ['cleaning_rate_m2_h', 'Скорость уборки', 'м²/ч'],
    ['picks_per_min_max', 'Захваты/мин', ''],
    ['flight_time_min', 'Время полёта', 'мин'],
    ['scan_rate_m2_h', 'Сканирование', 'м²/ч'],
    ['max_scan_height_m', 'Высота', 'м'],
    ['position_accuracy_cm', 'Точность', 'см'],
  ];

  return (
    <div className="mt-4 bg-white rounded-xl border p-4 overflow-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm">
          Сравнение характеристик ({robots.length})
        </h3>
        <button
          onClick={onClose}
          className="text-xs text-slate-400 hover:text-slate-600"
        >
          ✕ закрыть
        </button>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-left">
            <th className="py-2 pr-4 text-slate-400 font-normal">Параметр</th>
            {robots.map((rb) => (
              <th key={rb.id} className="py-2 px-4 font-semibold text-[11px]">
                {ROBOT_ICONS[rb.id] || '▪'} {rb.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fieldsToShow.map(([key, label, unit]) => {
            // Показываем строку только если у кого-то из сравнимых есть это поле
            const anyHas = robots.some((rb) => rb.specs[key] != null && rb.specs[key] !== 0);
            if (!anyHas) return null;
            return (
              <tr key={key} className="border-b">
                <td className="py-2 pr-4 text-slate-500">{label}</td>
                {robots.map((rb) => {
                  const v = rb.specs[key];
                  const display = v == null || v === 0 ? '—' : `${v}${unit ? ' ' + unit : ''}`;
                  return (
                    <td key={rb.id} className="py-2 px-4 font-semibold">
                      {display}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          <tr className="border-b">
            <td className="py-2 pr-4 text-slate-500">Навигация</td>
            {robots.map((rb) => (
              <td key={rb.id} className="py-2 px-4">
                {rb.specs.navigation_type || '—'}
              </td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="py-2 pr-4 text-slate-500">Цена</td>
            {robots.map((rb) => (
              <td key={rb.id} className="py-2 px-4 font-semibold">
                {fmtPrice(rb)}
              </td>
            ))}
          </tr>
          <tr>
            <td className="py-2 pr-4 text-slate-500">Происхождение цены</td>
            {robots.map((rb) => (
              <td key={rb.id} className="py-2 px-4 text-[10px] text-slate-400">
                {rb.price?.note || '—'}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
