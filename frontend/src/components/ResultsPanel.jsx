import { useEffect, useRef, useState } from 'react';
import AddProcessModal from './AddProcessModal';
import ZonalResults from './ZonalResults';
import DashboardOverview from './DashboardOverview';

const API = import.meta.env.VITE_API_URL || '';

const money = (n) =>
  Math.abs(n) >= 1e6
    ? `${(n / 1e6).toFixed(1)} млн ₽`
    : `${Math.round(n / 1e3)} тыс ₽`;

const SCEN = {
  pessimistic: 'Пессимистичный',
  base: 'Базовый',
  optimistic: 'Оптимистичный',
};

const PLABELS = {
  pallets_per_day: 'объём',
  area_m2: 'площадь',
  avg_distance_m: 'плечо',
  shifts_count: 'смены',
  staff_headcount: 'штат',
  released_headcount: 'высвобождение',
  horizon_years: 'горизонт',
  fte_cost_rub: 'зарплата',
  aisle_width_m: 'проходы',
  payload_kg: 'вес',
  discount_rate: 'ставка',
};

const HORIZON_HINTS = {
  5: 'Базовый: быстрое ТЭО',
  6: 'Учтён полный цикл батареи (5-6 лет)',
  7: 'Сбалансированный горизонт',
  8: 'Учтена вторая замена батарей (если применимо)',
  9: 'Долгосрочный горизонт',
  10: 'Полный жизненный цикл парка роботов',
};

function PROC_LABEL(pt) {
  return (
    {
      transport: 'Транспортировка',
      palletizing: 'Паллетизация',
      cleaning: 'Уборка',
      delivery: 'Доставка',
    }[pt] || 'Процесс'
  );
}

export default function ResultsPanel({
  result,
  userInput,
  onRecalc,
  onRestart,
}) {
  const [scenario, setScenario] = useState('base');
  const [robots, setRobots] = useState([]);
  const [checked, setChecked] = useState({});
  const [form, setForm] = useState({
    shifts: userInput.shifts_count || 2,
    fteMonth: Math.round((userInput.fte_cost_rub || 1249920) / 15.624 / 1000),
    staff: userInput.staff_headcount || 10,
    released: userInput.released_headcount ?? null,
    horizon: userInput.horizon_years || 5,
    discount: Math.round((userInput.discount_rate || 0.15) * 100),
    fleet: undefined,
  });
  const [extraProcesses, setExtraProcesses] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [expandedExtra, setExpandedExtra] = useState(null);
  const extraTimersRef = useRef({});
  const onRecalcRef = useRef(onRecalc);
  const userInputRef = useRef(userInput);

  useEffect(() => {
    onRecalcRef.current = onRecalc;
    userInputRef.current = userInput;
  }, [onRecalc, userInput]);

  useEffect(() => {
    fetch(`${API}/api/robots`)
      .then((r) => r.json())
      .then(setRobots)
      .catch(() => {});
  }, []);

  // ─── Whole-режим: реакция на изменения формы ───
  useEffect(() => {
    if (userInputRef.current?.mode === 'zonal') return;
    const id = setTimeout(() => {
      onRecalcRef.current({
        ...userInputRef.current,
        shifts_count: form.shifts,
        fte_cost_rub: Math.round(form.fteMonth * 1000 * 15.624),
        staff_headcount: form.staff,
        released_headcount: form.released,
        horizon_years: form.horizon,
        discount_rate: form.discount / 100,
        fleet_override: form.fleet,
      });
    }, 400);
    return () => clearTimeout(id);
  }, [form]);

  if (!result) return <div className="p-10 text-slate-400">Расчёт…</div>;

  // ─── Zonal-режим: отдельный экран ───
  if (result.mode === 'zonal') {
    return (
      <ZonalResults
        result={result}
        userInput={userInput}
        onRecalc={onRecalc}
        onRestart={onRestart}
      />
    );
  }

  const dq = result.data_quality;
  const mb = result.manual_baseline;
  const best = result.recommendations?.find((item) => item.is_best) || null;
  const selectedIds = userInput.selected_robot_ids || [];
  const compareIds = [
    ...new Set([
      ...selectedIds,
      ...Object.keys(checked).filter((k) => checked[k]),
    ]),
  ];
  const recommendedQty = best?.quantity ?? 1;
  const fleetMax = Math.max(15, recommendedQty + 5);
  const horizon =
    result.assumptions?.horizon_years || userInput.horizon_years || 5;
  const allResults = [
    { result, label: PROC_LABEL(userInput?.process_type) },
    ...extraProcesses,
  ];
  const hasMultiple = extraProcesses.length > 0;

  const getSc = (proc) => {
    const b = proc.result?.recommendations?.find((item) => item.is_best);
    if (!b) return null;
    return b.scenarios?.find((x) => x.scenario === scenario) || b;
  };

  const scResults = allResults.map(getSc).filter(Boolean);

  const totalCapex = scResults.reduce((sum, s) => sum + (s?.capex || 0), 0);
  const totalSavings = scResults.reduce(
    (sum, s) => sum + (s?.savings_annual || 0),
    0
  );
  const totalOpex = scResults.reduce(
    (sum, s) => sum + (s?.opex_annual || 0),
    0
  );
  const totalRobots = scResults.reduce(
    (sum, s) => sum + (s?.quantity || 0),
    0
  );

  const totalDisplaced = allResults.reduce(
    (sum, p) => sum + (p.result?.recommendations?.find((item) => item.is_best)?.fte_displaced || 0),
    0
  );

  const combinedNet = totalSavings - totalOpex;
  const combinedPayback =
    combinedNet > 0
      ? Math.round((totalCapex / combinedNet) * 10) / 10
      : 99;

  const handleAddProcess = (processData) => {
    setExtraProcesses((prev) => [...prev, processData]);
    setShowAddModal(false);
    setExpandedExtra(extraProcesses.length);
  };

  const removeExtraProcess = (index) => {
    clearTimeout(extraTimersRef.current[index]);
    setExtraProcesses((prev) => prev.filter((_, i) => i !== index));
    setExpandedExtra(null);
  };

  const recalcExtraProcess = async (idx, formData) => {
    const ep = extraProcesses[idx];
    if (!ep) return;

    const isCleaning = ep.input?.process_type === 'cleaning';
    const newInput = {
      ...ep.input,
      shifts_count: formData.shifts,
      fte_cost_rub: Math.round(formData.salary * 1000 * 15.624),
      area_m2: isCleaning ? formData.volume : ep.input?.area_m2,
      pallets_per_day: !isCleaning
        ? formData.volume
        : ep.input?.pallets_per_day,
    };

    try {
      const res = await fetch(`${API}/api/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newInput),
      });
      if (!res.ok) return;
      const newResult = await res.json();
      setExtraProcesses((prev) =>
        prev.map((p, i) =>
          i === idx ? { ...p, input: newInput, result: newResult } : p
        )
      );
    } catch (e) {
      console.error('Extra recalc error:', e);
    }
  };

  const handleExtraChange = (idx, formData) => {
    clearTimeout(extraTimersRef.current[idx]);
    extraTimersRef.current[idx] = setTimeout(() => {
      recalcExtraProcess(idx, formData);
    }, 500);
  };

  const robotStatus = (robot) => {
    const rec = result.recommendations.find((r) => r.robot_id === robot.id);
    if (rec) {
      if (rec.forced) return { s: 'selected', label: 'Ваш Выбор' };
      if (rec.is_best)
        return { s: 'star', label: '★ Рекомендован' };
      return { s: 'ok', label: 'Совместим' };
    }
    if (robot.category === 'aerial') {
      return { s: 'na', label: 'Отдельная ветка' };
    }
    const rej = result.rejected.find((r) => r.robot_id === robot.id);
    if (rej) return { s: 'rejected', label: 'Отклонён' };
    return { s: 'na', label: '—' };
  };

  const resetSelection = () => {
    setChecked({});
    onRecalc({ ...userInput, selected_robot_ids: [] });
  };

  const addForced = (robotId) => {
    onRecalc({
      ...userInput,
      selected_robot_ids: [...new Set([...selectedIds, robotId])],
    });
  };

  const applyCompared = () => {
    onRecalc({ ...userInput, selected_robot_ids: compareIds });
  };

  const compareSpec = robots.filter((rb) => {
    const rec = result.recommendations.find((r) => r.robot_id === rb.id);
    return checked[rb.id] || (rec && rec.forced);
  });

  const fleetLabel = form.fleet
    ? `${form.fleet} шт · ручной`
    : `${recommendedQty} шт · авто`;

  const updateStaff = (newStaff) => {
    const s = Math.max(1, newStaff || 1);
    const r = form.released;
    const newReleased = r != null && r > s ? s : r;
    setForm({ ...form, staff: s, released: newReleased });
  };

  const setReleased = (v) => {
    setForm({ ...form, released: v === form.staff ? null : v });
  };

  const bestStaff = best?.staff_breakdown;
  const sliderMaxRaw = bestStaff?.slider_enabled
    ? Math.floor(bestStaff.staff_replaceable)
    : form.staff;
  const sliderMax = Math.max(
    0,
    Math.min(form.staff, sliderMaxRaw || form.staff)
  );
  const sliderValue = Math.min(form.released ?? sliderMax, sliderMax);

  return (
    <div className="results-screen">
      <main className="results-main">
        <DashboardOverview result={result} userInput={userInput} />
        <section className="detailed-analysis" aria-label="Детальный расчёт">
        {result.warnings?.map((warning) => (
          <div
            key={warning}
            className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          >
            {warning}
          </div>
        ))}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">
            {hasMultiple
              ? 'Комбинированное ТЭО роботизации'
              : 'Предварительное ТЭО роботизации'}
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-xs px-2 py-1 rounded-full bg-slate-200">
              Горизонт: {horizon} лет
            </span>
            <span className="text-xs px-2 py-1 rounded-full bg-slate-200">
              Детализация: {dq.level} · {dq.completeness_pct}%
            </span>
            <button
              onClick={onRestart}
              className="text-sm text-slate-500 underline"
            >
              новый расчёт
            </button>
          </div>
        </div>

        {dq.assumed.length > 0 && (
          <div className="text-xs text-slate-500 bg-amber-50 border border-amber-200 rounded-xl p-3">
            <b>Допущения:</b>{' '}
            {dq.assumed.map((k) => PLABELS[k] || k).join(', ')}
            {dq.refine_priority.length > 0 && (
              <>
                {' '}
                · уточните:{' '}
                {dq.refine_priority
                  .slice(0, 3)
                  .map((k) => PLABELS[k] || k)
                  .join(' → ')}
              </>
            )}
          </div>
        )}

        {hasMultiple && (
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl p-5">
            <h2 className="font-bold text-sm uppercase tracking-wide mb-3">
              Комбинированное ТЭО · {SCEN[scenario]} ({allResults.length}{' '}
              процесса)
            </h2>
            <div className="grid grid-cols-5 gap-3 text-center">
              <div>
                <div className="text-[10px] text-blue-200">Роботов</div>
                <div className="text-xl font-bold">{totalRobots}</div>
              </div>
              <div>
                <div className="text-[10px] text-blue-200">CAPEX</div>
                <div className="text-xl font-bold">{money(totalCapex)}</div>
              </div>
              <div>
                <div className="text-[10px] text-blue-200">Экономия/год</div>
                <div className="text-xl font-bold">{money(totalSavings)}</div>
              </div>
              <div>
                <div className="text-[10px] text-blue-200">Высвобождено</div>
                <div className="text-xl font-bold">
                  {Math.round(totalDisplaced)} FTE
                </div>
              </div>
              <div>
                <div className="text-[10px] text-blue-200">Окупаемость</div>
                <div className="text-xl font-bold">
                  {combinedPayback > 10 ? '> 10' : combinedPayback} лет
                </div>
              </div>
            </div>
            <div className="text-[10px] text-blue-200 mt-3">
              {allResults.map((p) => p.label).join(' + ')}
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl border p-4">
          <h2 className="font-semibold text-sm text-slate-600">
            Без роботизации (baseline)
          </h2>
          <div className="text-sm mt-1">
            {mb.manual_fte} FTE
            {mb.forklifts ? ` + ${mb.forklifts} ричтраков` : ''} · ≈{' '}
            {money(mb.total_cost_annual)}/год · {money(mb.total_horizon)} за{' '}
            {mb.horizon_years || horizon} лет · ≈ {mb.cost_per_move}{' '}
            ₽/операция
          </div>
        </div>

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

        {result.recommendations.map((r) => {
          const s = r.scenarios.find((x) => x.scenario === scenario);
          const sb = r.staff_breakdown;
          const rHorizon = r.horizon_years || horizon;
          return (
            <div
              key={r.robot_id}
              className={`bg-white rounded-xl border p-4 ${
                r.is_best && !r.forced ? 'border-2 border-blue-400' : ''
              }`}
            >
              <div className="flex justify-between items-center">
                <h2 className="font-semibold">
                  {r.is_best && !r.forced && (
                    <span className="text-blue-600 mr-1">★</span>
                  )}
                  {r.robot_name} × {s.quantity}
                  {r.forced && (
                    <span className="ml-2 text-xs text-amber-600 font-semibold">
                      выбор клиента
                    </span>
                  )}
                  {form.fleet && !r.forced && r.is_best && (
                    <span className="ml-2 text-xs text-amber-500 font-semibold">
                      частичная ({form.fleet} шт)
                    </span>
                  )}
                </h2>
                <span className="text-sm text-slate-500">
                  Readiness: {r.readiness_score}/100
                </span>
              </div>

              <div className="grid grid-cols-6 gap-2 text-center text-sm mt-3">
                <Metric label="CAPEX" value={money(s.capex)} />
                <Metric label="Экономия/год" value={money(s.savings_annual)} />
                <Metric
                  label="OPEX/год"
                  value={money(r.opex_breakdown.total)}
                />
                <Metric
                  label="Окупаемость"
                  value={
                    s.payback_years > rHorizon
                      ? `> ${rHorizon} лет`
                      : `${s.payback_years} лет`
                  }
                />
                <Metric label={`NPV ${rHorizon} лет`} value={money(s.npv)} />
                <Metric label="₽/операция" value={`${s.cost_per_move} ₽`} />
              </div>

              <div className="text-xs text-slate-500 mt-2">
                Роботы {money(r.capex_breakdown.robots)} → проект{' '}
                {money(r.capex_breakdown.total)} → TCO за {rHorizon} лет{' '}
                {money(r.tco)}
                {' · '}потенциал замены {r.fte_displaced} FTE
                {' · '}реально высвобождается {r.fte_released} FTE
                {' · '}загрузка {Math.round(r.fleet_utilization * 100)}%
              </div>

              {sb?.slider_enabled && (
                <div className="text-xs text-slate-600 mt-2 bg-slate-50 rounded p-2 border border-slate-100">
                  <div className="font-semibold text-slate-700 mb-1">
                    Раскладка по персоналу
                  </div>
                  <div className="space-y-0.5 text-[11px]">
                    {sb.staff_requested != null && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">
                          Хотите заменить:
                        </span>
                        <b>{sb.staff_requested} чел.</b>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-slate-500">
                        Робот может заменить:
                      </span>
                      <b>{sb.staff_replaceable.toFixed(0)} FTE</b>
                    </div>
                    {sb.is_clamped && (
                      <div className="flex justify-between text-amber-600">
                        <span>Применено к расчёту:</span>
                        <b>{sb.staff_applied.toFixed(0)} чел.</b>
                      </div>
                    )}
                    <div className="flex justify-between border-t border-slate-200 pt-0.5 mt-0.5">
                      <span className="text-slate-500">
                        Останется на пульте:
                      </span>
                      <b>{sb.staff_on_pult.toFixed(0)} FTE</b>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">
                        Реально высвободится:
                      </span>
                      <b className="text-green-700">
                        {sb.staff_released.toFixed(0)} FTE
                      </b>
                    </div>
                    {sb.pult_shortage > 0 && (
                      <div className="flex justify-between text-amber-600 border-t border-amber-200 pt-0.5 mt-0.5">
                        <span>⚠ Не хватает операторов:</span>
                        <b>{sb.pult_shortage.toFixed(0)} FTE</b>
                      </div>
                    )}
                  </div>
                  {sb.pult_shortage > 0 && (
                    <div className="text-[10px] text-amber-600 mt-1 bg-amber-50 border border-amber-100 rounded px-2 py-1">
                      Из заменённых не хватает на пульт — потребуется перевод
                      из незаменённых
                    </div>
                  )}
                  {sb.pult_reason === 'min_per_shift' &&
                    sb.pult_shortage === 0 && (
                      <div className="text-[10px] text-slate-400 mt-1">
                        На пульте сработал минимум:{' '}
                        {sb.min_pult_per_shift} чел. × {sb.pult_minimum} смен
                      </div>
                    )}
                </div>
              )}

              <div className="text-[10px] text-slate-400 mt-1">
                {r.price_note}
              </div>

              <ul className="text-xs text-slate-500 mt-2 list-disc pl-4">
                {r.warnings.slice(0, 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          );
        })}

        {extraProcesses.map((ep, epIdx) => {
          const eb = ep.result?.recommendations?.find((item) => item.is_best);
          if (!eb) return null;
          const es = eb.scenarios?.find((x) => x.scenario === scenario) || eb;
          const epHorizon = eb.horizon_years || horizon;
          return (
            <div
              key={epIdx}
              className="bg-white rounded-xl border-2 border-blue-200 p-4 relative"
            >
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700 font-semibold">
                    {ep.label}
                  </span>
                  <h3 className="font-semibold mt-2">
                    {eb.robot_name} × {es.quantity}
                  </h3>
                </div>
                <button
                  onClick={() => removeExtraProcess(epIdx)}
                  className="text-xs text-red-400 hover:text-red-600"
                >
                  ✕ убрать
                </button>
              </div>
              <div className="grid grid-cols-4 gap-2 text-center text-sm mt-3">
                <Metric label="CAPEX" value={money(es.capex)} />
                <Metric label="Экономия/год" value={money(es.savings_annual)} />
                <Metric
                  label="Окупаемость"
                  value={
                    es.payback_years > epHorizon
                      ? `> ${epHorizon} лет`
                      : `${es.payback_years} лет`
                  }
                />
                <Metric label="FTE" value={String(eb.fte_displaced)} />
              </div>
              <ul className="text-xs text-slate-500 mt-2 list-disc pl-4">
                {eb.warnings?.slice(0, 2).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          );
        })}

        <button
          onClick={() => setShowAddModal(true)}
          className="w-full border-2 border-dashed border-slate-300 rounded-xl py-3 text-sm text-slate-500 hover:border-blue-400 hover:text-blue-600 transition"
        >
          ➕ Добавить другой процесс (уборка, доставка, паллетизация)
        </button>

        {showAddModal && (
          <AddProcessModal
            objectType={userInput?.object_type || 'retail'}
            sharedParams={userInput}
            onAdd={handleAddProcess}
            onClose={() => setShowAddModal(false)}
          />
        )}

        {result.rejected.length > 0 && (
          <div className="text-xs text-slate-400">
            Отклонено:{' '}
            {result.rejected
              .map((r) => `${r.robot_name} — ${r.reason}`)
              .join('; ')}
          </div>
        )}

        <div className="bg-white rounded-xl border p-4">
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-semibold text-sm">
              Каталог решений ({robots.length})
            </h3>
            <div className="flex items-center gap-2">
              {selectedIds.length > 0 && (
                <button
                  onClick={resetSelection}
                  className="text-xs text-red-500 underline"
                >
                  ✕ сбросить выбор ({selectedIds.length})
                </button>
              )}
              {compareIds.length > 0 && (
                <button
                  onClick={applyCompared}
                  className="bg-blue-600 text-white rounded-lg px-3 py-1 text-xs"
                >
                  Пересчитать с выбранными ({compareIds.length})
                </button>
              )}
            </div>
          </div>

          <div className="space-y-1">
            {robots.map((rb) => {
              const st = robotStatus(rb);
              const inRecs = !!result.recommendations.find(
                (r) => r.robot_id === rb.id
              );
              return (
                <div
                  key={rb.id}
                  className="flex items-center justify-between text-xs border-b py-1.5"
                >
                  <div className="flex items-center gap-2">
                    {!inRecs && st.s !== 'na' && (
                      <input
                        type="checkbox"
                        checked={!!checked[rb.id]}
                        onChange={(e) =>
                          setChecked({
                            ...checked,
                            [rb.id]: e.target.checked,
                          })
                        }
                      />
                    )}
                    <span className="font-medium">{rb.name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-right">
                    <span className="text-slate-500">
                      {rb.economics.robot_capex_rub
                        ? money(rb.economics.robot_capex_rub)
                        : 'по запросу'}
                    </span>
                    <span
                      className={
                        st.s === 'star'
                          ? 'text-blue-600 font-semibold'
                          : st.s === 'selected'
                            ? 'text-amber-600'
                            : st.s === 'rejected'
                              ? 'text-slate-400'
                              : 'text-green-600'
                      }
                    >
                      {st.label}
                    </span>
                    {st.s === 'rejected' && (
                      <button
                        onClick={() => addForced(rb.id)}
                        className="underline text-blue-600"
                      >
                        посчитать
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {result.rejected.length > 0 && (
            <div className="text-[10px] text-slate-400 mt-2">
              Отметьте галочками для сравнения характеристик
            </div>
          )}
        </div>

        {compareSpec.length >= 2 && (
          <div className="bg-white rounded-xl border p-4 overflow-auto">
            <h3 className="font-semibold text-sm mb-3">
              Сравнение характеристик ({compareSpec.length})
            </h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2 pr-4 text-slate-400 font-normal">
                    Параметр
                  </th>
                  {compareSpec.map((rb) => (
                    <th
                      key={rb.id}
                      className="py-2 px-4 font-semibold text-[11px]"
                    >
                      {rb.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-2 pr-4 text-slate-500">
                    Грузоподъёмность
                  </td>
                  {compareSpec.map((rb) => (
                    <td key={rb.id} className="py-2 px-4 font-semibold">
                      {rb.specs.payload_kg || '—'} кг
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4 text-slate-500">Скорость</td>
                  {compareSpec.map((rb) => (
                    <td key={rb.id} className="py-2 px-4 font-semibold">
                      {rb.specs.max_speed_m_s || '—'} м/с
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4 text-slate-500">Автономность</td>
                  {compareSpec.map((rb) => (
                    <td key={rb.id} className="py-2 px-4 font-semibold">
                      {rb.specs.autonomy_hours || '—'} ч
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4 text-slate-500">Мин. проход</td>
                  {compareSpec.map((rb) => (
                    <td key={rb.id} className="py-2 px-4 font-semibold">
                      {rb.specs.min_aisle_width_m || '—'} м
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4 text-slate-500">Навигация</td>
                  {compareSpec.map((rb) => (
                    <td key={rb.id} className="py-2 px-4">
                      {rb.specs.navigation_type}
                    </td>
                  ))}
                </tr>
                {compareSpec.some((rb) => rb.specs.cleaning_rate_m2_h) && (
                  <tr className="border-b">
                    <td className="py-2 pr-4 text-slate-500">
                      Скорость уборки
                    </td>
                    {compareSpec.map((rb) => (
                      <td key={rb.id} className="py-2 px-4 font-semibold">
                        {rb.specs.cleaning_rate_m2_h
                          ? `${rb.specs.cleaning_rate_m2_h} м²/ч`
                          : '—'}
                      </td>
                    ))}
                  </tr>
                )}
                {compareSpec.some((rb) => rb.specs.picks_per_min_max) && (
                  <tr className="border-b">
                    <td className="py-2 pr-4 text-slate-500">Захваты/мин</td>
                    {compareSpec.map((rb) => (
                      <td key={rb.id} className="py-2 px-4 font-semibold">
                        {rb.specs.picks_per_min_max || '—'}
                      </td>
                    ))}
                  </tr>
                )}
                <tr className="border-b">
                  <td className="py-2 pr-4 text-slate-500">Цена</td>
                  {compareSpec.map((rb) => (
                    <td key={rb.id} className="py-2 px-4 font-semibold">
                      {rb.economics.robot_capex_rub
                        ? `${(rb.economics.robot_capex_rub / 1e6).toFixed(1)} млн ₽`
                        : 'по запросу'}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2 pr-4 text-slate-500">Происхождение</td>
                  {compareSpec.map((rb) => (
                    <td
                      key={rb.id}
                      className="py-2 px-4 text-[10px] text-slate-400"
                    >
                      {rb.price?.note || '—'}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        </section>
      </main>

      <aside className="what-if-panel panel" aria-label="What-If анализ">
        <h3 className="font-semibold text-sm">What-If анализ</h3>

        <div className="text-xs font-semibold text-slate-600 border-b pb-1">
          {PROC_LABEL(userInput?.process_type)}
        </div>

        <label className="block text-xs text-slate-500">
          Зарплата: {form.fteMonth} тыс ₽/мес
          <input
            type="range"
            min={30}
            max={200}
            step={5}
            value={form.fteMonth}
            onChange={(e) => setForm({ ...form, fteMonth: +e.target.value })}
            className="w-full"
          />
        </label>

        <label className="block text-xs text-slate-500">
          Смен: {form.shifts}
          <input
            type="range"
            min={1}
            max={3}
            step={1}
            value={form.shifts}
            onChange={(e) => setForm({ ...form, shifts: +e.target.value })}
            className="w-full"
          />
        </label>

        <label className="block text-xs text-slate-500">
          Текущий штат, чел
          <input
            type="number"
            min={1}
            max={200}
            value={form.staff}
            onChange={(e) => updateStaff(+e.target.value)}
            className="w-full border rounded-lg px-2 py-1.5 text-sm mt-0.5"
          />
        </label>

        <div className="border border-slate-200 rounded-lg p-2 bg-slate-50">
          <div className="text-xs">
            <div className="font-semibold text-slate-700 text-sm">
              Сколько сотрудников заменить роботами
            </div>
            <div className="text-[10px] text-slate-400 mb-1">
              Двигайте ползунок: роботы возьмут на себя часть работы
            </div>
            <div className="text-slate-600 mb-1">
              {form.released == null ? (
                <span className="text-slate-400">
                  Заменить всех, кого может робот
                </span>
              ) : form.released === 0 ? (
                <span className="text-slate-400">Никого не заменяем</span>
              ) : (
                <span>
                  Хотите заменить <b>{form.released}</b> из {form.staff}{' '}
                  человек
                </span>
              )}
            </div>
          </div>
          <input
            type="range"
            min={0}
            max={sliderMax}
            step={1}
            value={sliderValue}
            onChange={(e) => setReleased(+e.target.value)}
            className="w-full"
          />
          <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
            <span>0</span>
            <span>все ({sliderMax})</span>
          </div>
          {sliderMax < form.staff && (
            <span className="text-[10px] text-amber-500">
              Робот может заменить максимум {sliderMax} FTE (ограничение по
              производительности и сменам)
            </span>
          )}
          {sliderMax === form.staff && (
            <span className="text-[10px] text-slate-400">
              Не менее 1 человека на смену остаётся на пульте
            </span>
          )}
        </div>

        <label className="block text-xs text-slate-500">
          Горизонт: {form.horizon} лет
          <input
            type="range"
            min={5}
            max={10}
            step={1}
            value={form.horizon}
            onChange={(e) => setForm({ ...form, horizon: +e.target.value })}
            className="w-full"
          />
          <span className="text-[10px] text-slate-400">
            {HORIZON_HINTS[form.horizon]}
          </span>
        </label>

        <label className="block text-xs text-slate-500">
          <div className="flex justify-between items-center">
            <span>Роботов: {fleetLabel}</span>
            {form.fleet && (
              <button
                onClick={() => setForm({ ...form, fleet: undefined })}
                className="text-[10px] text-blue-500 underline"
              >
                сбросить
              </button>
            )}
          </div>
          <input
            type="range"
            min={1}
            max={fleetMax}
            step={1}
            value={form.fleet ?? recommendedQty}
            onChange={(e) => setForm({ ...form, fleet: +e.target.value })}
            className="w-full"
          />
          {form.fleet ? (
            <span className="text-[10px] text-amber-500">
              Ручной режим: {form.fleet} шт
              {form.fleet < recommendedQty && (
                <span className="text-slate-400">
                  {' '}
                  (расчёт: {recommendedQty})
                </span>
              )}
            </span>
          ) : (
            <span className="text-[10px] text-slate-400">
              Автоматически: {recommendedQty} шт
            </span>
          )}
        </label>

        <label className="block text-xs text-slate-500">
          Ставка: {form.discount}%
          <input
            type="range"
            min={6}
            max={30}
            step={1}
            value={form.discount}
            onChange={(e) => setForm({ ...form, discount: +e.target.value })}
            className="w-full"
          />
        </label>

        {extraProcesses.map((ep, epIdx) => {
          const eb = ep.result?.recommendations?.find((item) => item.is_best);
          const isCleaning = ep.input?.process_type === 'cleaning';
          const volOriginal = isCleaning
            ? ep.input?.area_m2 || 6000
            : ep.input?.pallets_per_day || 500;
          const volMin = Math.max(1, Math.floor(volOriginal * 0.2));
          const volMax = Math.ceil(volOriginal * 3);
          const volStep = Math.max(1, Math.floor((volMax - volMin) / 40));
          const isExpanded = expandedExtra === epIdx;

          return (
            <div key={epIdx} className="border-t pt-3 mt-3">
              <button
                onClick={() => setExpandedExtra(isExpanded ? null : epIdx)}
                className="w-full flex items-center justify-between text-xs font-semibold text-blue-600 hover:text-blue-800"
              >
                <span>
                  {ep.label} ({eb?.quantity || '—'} роботов)
                </span>
                <span>{isExpanded ? '▼' : '▶'}</span>
              </button>

              {isExpanded && (
                <ExtraSliders
                  ep={ep}
                  idx={epIdx}
                  isCleaning={isCleaning}
                  volMin={volMin}
                  volMax={volMax}
                  volStep={volStep}
                  onChange={handleExtraChange}
                />
              )}
            </div>
          );
        })}

        <div className="text-xs text-slate-400 space-y-1 pt-2 border-t">
          <p className="font-semibold text-slate-500">Допущения модели:</p>
          <p>
            Утилизация:{' '}
            {result.assumptions.scenario_params[scenario]?.utilization}
          </p>
          <p>Горизонт: {horizon} лет</p>
          <p>Ротация: {result.assumptions.rotation_formula}</p>
          <p className="text-[10px] pt-1">{result.assumptions.note}</p>
        </div>
      </aside>
    </div>
  );
}

function ExtraSliders({
  ep,
  idx,
  isCleaning,
  volMin,
  volMax,
  volStep,
  onChange,
}) {
  const [local, setLocal] = useState({
    salary: Math.round((ep.input?.fte_cost_rub || 800000) / 15.624 / 1000),
    shifts: ep.input?.shifts_count || 2,
    volume: isCleaning
      ? ep.input?.area_m2 || 6000
      : ep.input?.pallets_per_day || 500,
  });

  const set = (key, value) => {
    const next = { ...local, [key]: value };
    setLocal(next);
    onChange(idx, next);
  };

  return (
    <div className="space-y-3 pt-2">
      <label className="block text-xs text-slate-500">
        Зарплата: {local.salary} тыс ₽/мес
        <input
          type="range"
          min={30}
          max={150}
          step={5}
          value={local.salary}
          onChange={(e) => set('salary', +e.target.value)}
          className="w-full"
        />
      </label>

      <label className="block text-xs text-slate-500">
        Смен: {local.shifts}
        <input
          type="range"
          min={1}
          max={3}
          step={1}
          value={local.shifts}
          onChange={(e) => set('shifts', +e.target.value)}
          className="w-full"
        />
      </label>

      <label className="block text-xs text-slate-500">
        {isCleaning ? 'Площадь: ' : 'Объём: '}
        {local.volume} {isCleaning ? 'м²' : 'шт/сутки'}
        <input
          type="range"
          min={volMin}
          max={volMax}
          step={volStep}
          value={local.volume}
          onChange={(e) => set('volume', +e.target.value)}
          className="w-full"
        />
      </label>
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
