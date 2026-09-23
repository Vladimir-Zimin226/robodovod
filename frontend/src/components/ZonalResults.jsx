import { useEffect, useRef, useState } from 'react';
import ZonalDashboardOverview from './ZonalDashboardOverview';

const money = (n) =>
  Math.abs(n) >= 1e6
    ? `${(n / 1e6).toFixed(1)} млн ₽`
    : `${Math.round(n / 1e3)} тыс ₽`;

const PROCESS_LABEL = {
  transport: 'Транспортировка',
  palletizing: 'Паллетизация',
  cleaning: 'Уборка',
  delivery: 'Доставка',
};

const PROCESS_ICON = {
  transport: '🚚',
  palletizing: '🤖',
  cleaning: '🧹',
  delivery: '🛎',
};

const SCEN = {
  pessimistic: 'Пессимистичный',
  base: 'Базовый',
  optimistic: 'Оптимистичный',
};

const HORIZON_HINTS = {
  5: 'Базовый: быстрое ТЭО',
  6: 'Учтён полный цикл батареи',
  7: 'Сбалансированный горизонт',
  8: 'Учтена вторая замена батарей',
  9: 'Долгосрочный горизонт',
  10: 'Полный жизненный цикл парка',
};

// ─── Границы ползунков (фиксируются от baseline) ───
const STAFF_MIN = 1;
const STAFF_MAX_FACTOR = 3;
const STAFF_MIN_CEIL = 20;
const STAFF_MAX_CEIL = 100;      // М1: верхний предел, чтобы не было 1500
const VOLUME_MIN_FACTOR = 0.2;
const VOLUME_MAX_FACTOR = 3;
const VOLUME_STEPS = 40;
const FLEET_MIN = 1;
const FLEET_MAX_FLOOR = 15;
const FLEET_MAX_MARGIN = 5;

export default function ZonalResults({
  result,
  userInput,
  onRecalc,
  onRestart,
}) {
  const [expandedZone, setExpandedZone] = useState(result.zones?.[0]?.zone_id);
  const [scenario, setScenario] = useState('base');

  const [shared, setShared] = useState(() => ({
    fteMonth: Math.round((userInput.fte_cost_rub || 1249920) / 15.624 / 1000),
    horizon: userInput.horizon_years || 5,
    discount: Math.round((userInput.discount_rate || 0.15) * 100),
  }));

  const [zoneParams, setZoneParams] = useState(() => {
    const init = {};
    (userInput.zones || []).forEach((z) => {
      const isCleaning = z.process_type === 'cleaning';
      init[z.id] = {
        volume: isCleaning ? z.area_m2 || 1000 : z.volume_per_day || 100,
        shifts: z.shifts_count || 2,
        staff: z.staff_headcount || 2,
        released: z.released_headcount ?? null,
        fleet: z.fleet_override ?? null,
      };
    });
    return init;
  });

  // ─── Baseline для границ ползунков ───
  const [baselines] = useState(() => {
    const init = {};
    (userInput.zones || []).forEach((z) => {
      const isCleaning = z.process_type === 'cleaning';
      init[z.id] = {
        staff: z.staff_headcount || 2,
        volume: isCleaning ? z.area_m2 || 1000 : z.volume_per_day || 100,
      };
    });
    return init;
  });

  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const userInputRef = useRef(userInput);
  const firstRenderRef = useRef(true);

  useEffect(() => {
    userInputRef.current = userInput;
  }, [userInput]);

  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    if (!dirty) return;

    const id = setTimeout(() => {
      const base = userInputRef.current;
      const newInput = {
        ...base,
        fte_cost_rub: Math.round(shared.fteMonth * 1000 * 15.624),
        horizon_years: shared.horizon,
        discount_rate: shared.discount / 100,
        zones: (base.zones || []).map((z) => {
          const p = zoneParams[z.id];
          if (!p) return z;
          const isCleaning = z.process_type === 'cleaning';
          return {
            ...z,
            volume_per_day: isCleaning ? z.volume_per_day : p.volume,
            area_m2: isCleaning ? p.volume : z.area_m2,
            shifts_count: p.shifts,
            staff_headcount: p.staff,
            released_headcount: p.released,
            fleet_override: p.fleet,
          };
        }),
      };
      setBusy(true);
      setDirty(false);
      Promise.resolve(onRecalc(newInput)).finally(() => setBusy(false));
    }, 600);

    return () => clearTimeout(id);
  }, [shared, zoneParams, dirty, onRecalc]);

  const updateShared = (k, v) => {
    setShared((s) => ({ ...s, [k]: v }));
    setDirty(true);
  };

  const updateZone = (id, k, v) => {
    setZoneParams((zp) => ({ ...zp, [id]: { ...zp[id], [k]: v } }));
    setDirty(true);
  };

  if (!result || result.mode !== 'zonal' || !result.combined) {
    return (
      <div className="p-10 text-slate-400">
        Нет данных для зонального расчёта
      </div>
    );
  }

  const c = result.combined;
  const horizon = c.horizon_years || 5;

  return (
    <div className="results-screen">
      <main className="results-main">
        <ZonalDashboardOverview result={result} userInput={userInput} />
        <section className="detailed-analysis" id="zone-details" aria-label="Детализация зон">
        {/* ─── Header ─── */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Зональное ТЭО роботизации</h1>
          <div className="flex items-center gap-3">
            {busy && (
              <span className="text-xs px-2 py-1 rounded-full bg-amber-100 text-amber-700 animate-pulse">
                Пересчёт…
              </span>
            )}
            <span className="text-xs px-2 py-1 rounded-full bg-slate-200">
              {c.zones_count} зон · {horizon} лет
            </span>
            <button
              onClick={onRestart}
              className="text-sm text-slate-500 underline"
            >
              новый расчёт
            </button>
          </div>
        </div>

        {/* ─── Комбинированная сводка ─── */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl p-5">
          <h2 className="font-bold text-sm uppercase tracking-wide mb-3">
            Комбинированное ТЭО · {SCEN[scenario]}
          </h2>
          <div className="grid grid-cols-6 gap-3 text-center">
            <div>
              <div className="text-[10px] text-blue-200">Зон</div>
              <div className="text-xl font-bold">{c.zones_count}</div>
            </div>
            <div>
              <div className="text-[10px] text-blue-200">Роботов всего</div>
              <div className="text-xl font-bold">{c.total_robots}</div>
            </div>
            <div>
              <div className="text-[10px] text-blue-200">CAPEX</div>
              <div className="text-xl font-bold">{money(c.total_capex)}</div>
            </div>
            <div>
              <div className="text-[10px] text-blue-200">Экономия/год</div>
              <div className="text-xl font-bold">
                {money(c.total_savings_annual)}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-blue-200">Высвобождено</div>
              <div className="text-xl font-bold">
                {c.total_released.toFixed(0)} FTE
              </div>
            </div>
            <div>
              <div className="text-[10px] text-blue-200">Окупаемость</div>
              <div className="text-xl font-bold">
                {c.combined_payback_years > 10
                  ? '> 10'
                  : c.combined_payback_years}{' '}
                лет
              </div>
            </div>
          </div>
          <div className="mt-3 text-[10px] text-blue-200">
            Warehouse-фикс: {money(c.warehouse_fixed_rub)} (учтён 1×)
            {c.best_zone_id &&
              ` · Лучшая зона: ${c.best_zone_id} (${c.best_zone_payback} лет)`}
          </div>
        </div>

        {/* ─── Переключатель сценария ─── */}
        <div className="flex gap-2">
          {Object.entries(SCEN).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setScenario(k)}
              className={`px-3 py-1 rounded-full text-sm ${
                scenario === k ? 'bg-blue-600 text-white' : 'bg-slate-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* ─── Зоны ─── */}
        {result.zones.map((z) => {
          const isOpen = expandedZone === z.zone_id;
          const best = z.recommendations.find(
            (r) => r.robot_id === z.best_robot_id
          );
          const p = zoneParams[z.zone_id] || {};
          const isCleaning = z.process_type === 'cleaning';
          const baseline = baselines[z.zone_id] || {
            staff: 2,
            volume: 100,
          };

          // ─── Границы ползунков от baseline ───
          const staffMax = Math.min(
            STAFF_MAX_CEIL,
            Math.max(
              STAFF_MIN_CEIL,
              Math.ceil(baseline.staff * STAFF_MAX_FACTOR)
            )
          );
          const volumeMin = Math.max(
            1,
            Math.floor(baseline.volume * VOLUME_MIN_FACTOR)
          );
          const volumeMax = Math.ceil(baseline.volume * VOLUME_MAX_FACTOR);
          const volumeStep = Math.max(
            1,
            Math.floor((volumeMax - volumeMin) / VOLUME_STEPS)
          );

          const releasedMax = p.staff || 1;
          const releasedValue =
            p.released == null ? releasedMax : Math.min(p.released, releasedMax);
          const isFullRelease =
            p.released == null || p.released >= releasedMax;

          // ─── Границы для ползунка роботов ───
          const bestQty = best?.quantity ?? 1;
          const fleetMax = Math.max(FLEET_MAX_FLOOR, bestQty + FLEET_MAX_MARGIN);
          const fleetValue =
            p.fleet == null ? bestQty : Math.min(p.fleet, fleetMax);
          const isAutoFleet = p.fleet == null;

          return (
            <div key={z.zone_id} className="bg-white rounded-xl border">
              <button
                onClick={() => setExpandedZone(isOpen ? null : z.zone_id)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{PROCESS_ICON[z.process_type]}</span>
                  <div className="text-left">
                    <div className="font-semibold">
                      {z.zone_name} ({z.zone_id})
                    </div>
                    <div className="text-xs text-slate-500">
                      {PROCESS_LABEL[z.process_type]} · {z.shifts_count} см ×{' '}
                      {z.shift_hours} ч
                      {z.volume_per_day && ` · ${z.volume_per_day}/сутки`}
                      {z.area_m2 && ` · ${z.area_m2} м²`}
                      {z.staff_headcount && ` · ${z.staff_headcount} чел`}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  {z.zone_robots > 0 && (
                    <>
                      <span>{z.zone_robots} роб.</span>
                      <span>{money(z.zone_capex)} CAPEX</span>
                      <span className="font-semibold">
                        {z.zone_payback_years > 10
                          ? '> 10'
                          : z.zone_payback_years}{' '}
                        лет
                      </span>
                    </>
                  )}
                  <span className="text-slate-400">{isOpen ? '▼' : '▶'}</span>
                </div>
              </button>

              {z.status !== 'RECOMMENDED' && (
                <div className="mx-4 mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  {z.status_message ||
                    'Для зоны не назначена приемлемая рекомендация'}
                </div>
              )}

              {isOpen && (
                <div className="border-t p-4 space-y-4">
                  {/* ─── Ползунки зоны ─── */}
                  <div className="bg-slate-50 rounded-lg p-3 grid grid-cols-2 gap-4">
                    <div className="col-span-2 text-[10px] uppercase tracking-wider text-slate-400">
                      What-If для зоны
                    </div>

                    {/* Объём / площадь */}
                    <label className="block text-xs text-slate-500 col-span-2">
                      {isCleaning ? 'Площадь' : 'Объём'}: {p.volume}{' '}
                      {isCleaning ? 'м²' : 'шт/сутки'}
                      <input
                        type="range"
                        min={volumeMin}
                        max={volumeMax}
                        step={volumeStep}
                        value={p.volume}
                        onChange={(e) =>
                          updateZone(z.zone_id, 'volume', +e.target.value)
                        }
                        className="w-full"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                        <span>{volumeMin}</span>
                        <span>{volumeMax}</span>
                      </div>
                    </label>

                    {/* Смены */}
                    <label className="block text-xs text-slate-500">
                      Смен в сутки: {p.shifts}
                      <input
                        type="range"
                        min={1}
                        max={4}
                        step={1}
                        value={p.shifts}
                        onChange={(e) =>
                          updateZone(z.zone_id, 'shifts', +e.target.value)
                        }
                        className="w-full"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                        <span>1</span>
                        <span>4</span>
                      </div>
                    </label>

                    {/* Штат в зоне */}
                    <label className="block text-xs text-slate-500">
                      Штат в зоне: {p.staff} чел
                      <input
                        type="range"
                        min={STAFF_MIN}
                        max={staffMax}
                        step={1}
                        value={p.staff}
                        onChange={(e) => {
                          const newStaff = +e.target.value;
                          const newReleased =
                            p.released != null && p.released > newStaff
                              ? newStaff
                              : p.released;
                          setZoneParams((zp) => ({
                            ...zp,
                            [z.zone_id]: {
                              ...zp[z.zone_id],
                              staff: newStaff,
                              released: newReleased,
                            },
                          }));
                          setDirty(true);
                        }}
                        className="w-full"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                        <span>{STAFF_MIN}</span>
                        <span>{staffMax}</span>
                      </div>
                    </label>

                    {/* Сколько заменить */}
                    <label className="block text-xs text-slate-500 col-span-2">
                      <div className="flex justify-between">
                        <span>Сколько сотрудников заменить</span>
                        <span className="text-slate-700 font-semibold">
                          {isFullRelease
                            ? 'полное'
                            : `${releasedValue} из ${releasedMax}`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={releasedMax}
                        step={1}
                        value={releasedValue}
                        onChange={(e) => {
                          const v = +e.target.value;
                          updateZone(
                            z.zone_id,
                            'released',
                            v === releasedMax ? null : v
                          );
                        }}
                        className="w-full"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                        <span>0</span>
                        <span>все ({releasedMax})</span>
                      </div>
                    </label>

                    {/* Роботов в зоне */}
                    {best && (
                      <label className="block text-xs text-slate-500 col-span-2">
                        <div className="flex justify-between">
                          <span>Роботов в зоне</span>
                          <span className="text-slate-700 font-semibold">
                            {isAutoFleet
                              ? `${bestQty} шт · авто`
                              : `${fleetValue} шт · ручной`}
                          </span>
                        </div>
                        <input
                          type="range"
                          min={FLEET_MIN}
                          max={fleetMax}
                          step={1}
                          value={fleetValue}
                          onChange={(e) => {
                            const v = +e.target.value;
                            updateZone(
                              z.zone_id,
                              'fleet',
                              v === bestQty ? null : v
                            );
                          }}
                          className="w-full"
                        />
                        <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                          <span>{FLEET_MIN}</span>
                          <span>{fleetMax}</span>
                        </div>
                        {!isAutoFleet && fleetValue !== bestQty && (
                          <span className="text-[10px] text-amber-500">
                            Ручной режим. Авто-расчёт: {bestQty} шт
                            {fleetValue < bestQty && (
                              <span className="text-slate-400">
                                {' '}
                                · частичная роботизация
                              </span>
                            )}
                            {fleetValue > bestQty && (
                              <span className="text-slate-400">
                                {' '}
                                · избыточные мощности
                              </span>
                            )}
                          </span>
                        )}
                        {isAutoFleet && (
                          <span className="text-[10px] text-slate-400">
                            Автоматически подобранное количество
                          </span>
                        )}
                      </label>
                    )}

                    {busy && (
                      <div className="col-span-2 text-[10px] text-amber-600">
                        Пересчёт…
                      </div>
                    )}
                  </div>

                  {/* ─── Результат по зоне ─── */}
                  {best ? (
                    <>
                      <div className="flex justify-between items-center">
                        <h3 className="font-semibold">
                          ⭐ {best.robot_name} × {best.quantity}
                        </h3>
                        <span className="text-xs text-slate-400">
                          Readiness {best.readiness_score}/100
                        </span>
                      </div>

                      <div className="grid grid-cols-5 gap-2 text-center text-xs">
                        <Metric label="CAPEX" value={money(best.capex)} />
                        <Metric
                          label="Экономия/год"
                          value={money(best.savings_per_year)}
                        />
                        <Metric
                          label="Окупаемость"
                          value={
                            best.payback_years > best.horizon_years
                              ? `> ${best.horizon_years}`
                              : `${best.payback_years} лет`
                          }
                        />
                        <Metric
                          label={`NPV ${best.horizon_years} лет`}
                          value={money(best.npv)}
                        />
                        <Metric
                          label="Высвобождено"
                          value={`${best.fte_released} FTE`}
                        />
                      </div>

                      {/* ─── Раскладка по персоналу ─── */}
                      <div className="text-xs text-slate-600 bg-slate-50 rounded p-2 border border-slate-100">
                        <div className="font-semibold text-slate-700 mb-1">
                          Раскладка по персоналу
                        </div>
                        <div className="space-y-0.5 text-[11px]">
                          {best.staff_breakdown.staff_requested != null && (
                            <div className="flex justify-between">
                              <span className="text-slate-500">
                                Хотите заменить:
                              </span>
                              <b>
                                {best.staff_breakdown.staff_requested} чел.
                              </b>
                            </div>
                          )}
                          <div className="flex justify-between">
                            <span className="text-slate-500">
                              Робот может заменить:
                            </span>
                            <b>
                              {best.staff_breakdown.staff_replaceable.toFixed(0)}{' '}
                              FTE
                            </b>
                          </div>
                          {best.staff_breakdown.is_clamped && (
                            <div className="flex justify-between text-amber-600">
                              <span>Применено к расчёту:</span>
                              <b>
                                {best.staff_breakdown.staff_applied.toFixed(0)}{' '}
                                чел.
                              </b>
                            </div>
                          )}
                          <div className="flex justify-between border-t border-slate-200 pt-0.5 mt-0.5">
                            <span className="text-slate-500">
                              Останется на пульте:
                            </span>
                            <b>
                              {best.staff_breakdown.staff_on_pult.toFixed(0)} FTE
                            </b>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-500">
                              Реально высвободится:
                            </span>
                            <b className="text-green-700">
                              {best.staff_breakdown.staff_released.toFixed(0)} FTE
                            </b>
                          </div>
                          {best.staff_breakdown.pult_shortage > 0 && (
                            <div className="flex justify-between text-amber-600 border-t border-amber-200 pt-0.5 mt-0.5">
                              <span>⚠ Не хватает операторов:</span>
                              <b>
                                {best.staff_breakdown.pult_shortage.toFixed(0)} FTE
                              </b>
                            </div>
                          )}
                        </div>
                        {best.staff_breakdown.pult_shortage > 0 && (
                          <div className="text-[10px] text-amber-600 mt-1 bg-amber-50 border border-amber-100 rounded px-2 py-1">
                            Из заменённых не хватает на пульт — потребуется перевод
                            из незаменённых
                          </div>
                        )}
                        {best.staff_breakdown.pult_reason === 'min_per_shift' &&
                          best.staff_breakdown.pult_shortage === 0 && (
                            <div className="text-[10px] text-slate-400 mt-1">
                              На пульте сработал минимум:{' '}
                              {best.staff_breakdown.min_pult_per_shift} чел. ×{' '}
                              {best.staff_breakdown.pult_minimum} смен
                            </div>
                          )}
                      </div>

                      <ul className="text-xs text-slate-500 list-disc pl-4">
                        {best.warnings
                          .filter(
                            (w) =>
                              !w.includes('Цена - оценка') &&
                              !w.includes('Предварительное ТЭО')
                          )
                          .slice(0, 4)
                          .map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                      </ul>

                      {z.recommendations.length > 1 && (
                        <div className="pt-2 border-t">
                          <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">
                            Альтернативы
                          </div>
                          {z.recommendations.slice(1, 4).map((r) => (
                            <div
                              key={r.robot_id}
                              className="flex justify-between text-xs py-1 border-b"
                            >
                              <span>
                                {r.robot_name} × {r.quantity}
                              </span>
                              <span className="text-slate-500">
                                {r.payback_years > 10
                                  ? '> 10'
                                  : r.payback_years}{' '}
                                лет · {money(r.capex)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-xs text-slate-400">
                      Не подобрано ни одного робота для этой зоны.
                      {z.rejected.length > 0 && (
                        <>
                          {' '}
                          Причины:{' '}
                          {z.rejected
                            .slice(0, 3)
                            .map((r) => r.reason)
                            .join('; ')}
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        <div className="flex justify-center gap-3 pt-2 pb-4">
          <button
            onClick={onRestart}
            className="rounded-xl px-6 py-3 text-sm font-semibold bg-slate-200 text-slate-700 hover:bg-slate-300"
          >
            🔄 Новый расчёт
          </button>
        </div>
        </section>
      </main>

      {/* ─── Правая панель ─── */}
      <aside className="what-if-panel panel" aria-label="What-If анализ по зонам">
        <h3 className="font-semibold text-sm">Общие параметры проекта</h3>

        <div className="text-xs text-slate-400 bg-slate-50 rounded p-2">
          Эти ползунки применяются ко всем зонам одновременно
        </div>

        <label className="block text-xs text-slate-500">
          Зарплата: {shared.fteMonth} тыс ₽/мес
          <input
            type="range"
            min={30}
            max={200}
            step={5}
            value={shared.fteMonth}
            onChange={(e) => updateShared('fteMonth', +e.target.value)}
            className="w-full"
          />
          <span className="text-[10px] text-slate-400">
            ≈ {((shared.fteMonth * 1000 * 12 * 1.55) / 1e6).toFixed(2)} млн ₽/год
            полной стоимости FTE
          </span>
        </label>

        <label className="block text-xs text-slate-500">
          Горизонт: {shared.horizon} лет
          <input
            type="range"
            min={5}
            max={10}
            step={1}
            value={shared.horizon}
            onChange={(e) => updateShared('horizon', +e.target.value)}
            className="w-full"
          />
          <span className="text-[10px] text-slate-400">
            {HORIZON_HINTS[shared.horizon]}
          </span>
        </label>

        <label className="block text-xs text-slate-500">
          Ставка дисконтирования: {shared.discount}%
          <input
            type="range"
            min={6}
            max={30}
            step={1}
            value={shared.discount}
            onChange={(e) => updateShared('discount', +e.target.value)}
            className="w-full"
          />
          <span className="text-[10px] text-slate-400">
            Используется в NPV и payback
          </span>
        </label>

        <div className="border-t pt-3 space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-500">Зон в проекте:</span>
            <b>{c.zones_count}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Роботов всего:</span>
            <b>{c.total_robots}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Warehouse-фикс:</span>
            <b>{money(c.warehouse_fixed_rub)}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Итого CAPEX:</span>
            <b>{money(c.total_capex)}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Экономия/год:</span>
            <b className="text-green-700">{money(c.total_savings_annual)}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">NPV за {horizon} лет:</span>
            <b>{money(c.total_npv)}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">TCO за {horizon} лет:</span>
            <b>{money(c.total_tco)}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Окупаемость:</span>
            <b>
              {c.combined_payback_years > 10
                ? '> 10 лет'
                : `${c.combined_payback_years} лет`}
            </b>
          </div>
        </div>

        {busy && (
          <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded p-2 text-center">
            ⏳ Пересчёт всех зон…
          </div>
        )}

        <div className="text-[10px] text-slate-400 pt-2 border-t">
          <p className="font-semibold text-slate-500 mb-1">Как это работает</p>
          <p>
            Общие ползунки применяются ко всем зонам. Ползунки внутри каждой
            зоны меняют только её. Парк суммируется, складские интеграции
            (Wi-Fi, WMS) учитываются один раз.
          </p>
        </div>
      </aside>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-slate-50 rounded p-2">
      <div className="text-[10px] text-slate-400">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
