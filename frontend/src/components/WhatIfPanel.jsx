import { useEffect, useRef, useState } from 'react';
import { buildWhatIfInput, DEFAULT_WHAT_IF, whatIfChanged, whatIfSummary } from '../whatIfModel.js';

const API = import.meta.env.VITE_API_URL || '';
const number = (value, digits = 0) => value == null ? 'Нужны данные'
  : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: digits }).format(Number(value));
const rubles = (value) => value == null ? 'Нужны данные' : `${number(value)} ₽`;
const percent = (value, status) => value == null ? status === 'N/A' || status?.startsWith('N/A')
  ? 'N/A: начальные вложения равны нулю' : 'Нужны данные' : `${number(value, 2)}%`;
const delta = (base, branch, unit = '₽') => base == null || branch == null ? '—'
  : `${Number(branch) - Number(base) > 0 ? '+' : ''}${number(Number(branch) - Number(base), 2)} ${unit}`;

function Slider({ label, value, onChange, min = -50, max = 100, unit = '%', base }) {
  return <label className="what-if-field"><span>{label}: <strong>{value > 0 ? '+' : ''}{value}{unit}</strong></span>
    <input type="range" min={min} max={max} step="1" value={value}
      onChange={(event) => onChange(Number(event.target.value))} />
    {base != null && <small>База: {base}</small>}</label>;
}

function Metrics({ title, summary, horizon, baseline }) {
  const cells = [
    ['Парк', summary.fleet, baseline && delta(baseline.fleet, summary.fleet, 'роб.')],
    ['Покупка · CAPEX', rubles(summary.purchase.capex), baseline && delta(baseline.purchase.capex, summary.purchase.capex)],
    ['Покупка · NPV', rubles(summary.purchase.npv), baseline && delta(baseline.purchase.npv, summary.purchase.npv)],
    ['Покупка · ROI', percent(summary.purchase.roi), baseline && delta(baseline.purchase.roi, summary.purchase.roi, 'п.п.')],
    ['Покупка · окупаемость', summary.purchase.payback == null ? 'Не достигается или нужны данные'
      : `${number(summary.purchase.payback, 2)} лет`, baseline && delta(baseline.purchase.payback, summary.purchase.payback, 'года')],
    ['RaaS · CAPEX', rubles(summary.raas.capex), baseline && delta(baseline.raas.capex, summary.raas.capex)],
    ['RaaS · NPV', rubles(summary.raas.npv), baseline && delta(baseline.raas.npv, summary.raas.npv)],
    ['RaaS · ROI', percent(summary.raas.roi, summary.raas.roiStatus), baseline
      && delta(baseline.raas.roi, summary.raas.roi, 'п.п.')],
  ];
  return <section className="what-if-column"><h3>{title}</h3><p>Горизонт: {horizon} лет.</p>
    <dl>{cells.map(([label, value, difference]) => <div key={label}><dt>{label}</dt><dd>{value}
      {difference && <small>Δ {difference}</small>}</dd></div>)}</dl>
    {summary.simulations.length > 0 && <p>Маршрут: {summary.simulations.map((sim) =>
      `${sim.status}, цикл ${sim.cycle_s ?? '—'} с, парк ${sim.fleet_required ?? '—'}`).join('; ')}.</p>}
  </section>;
}

export default function WhatIfPanel({ input, report, onBranch }) {
  const [controls, setControls] = useState({ ...DEFAULT_WHAT_IF });
  const [branch, setBranch] = useState(null);
  const [failure, setFailure] = useState(null);
  const revision = useRef(0);
  const onBranchRef = useRef(onBranch);
  useEffect(() => { onBranchRef.current = onBranch; }, [onBranch]);
  const changed = whatIfChanged(controls);
  const key = JSON.stringify(controls);
  const current = changed && branch?.key === key ? branch.report : null;
  const error = changed && failure?.key === key ? failure.message : '';
  useEffect(() => {
    if (!changed) return undefined;
    const controller = new AbortController();
    const run = ++revision.current;
    const timer = window.setTimeout(async () => {
      try {
        const draft = buildWhatIfInput(input, report, controls);
        const path = report.kind ? `/api/v2/object-roles/${report.kind}/preview`
          : '/api/v2/warehouse-roles/preview';
        const response = await fetch(`${API}${path}`, { method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft), signal: controller.signal });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `HTTP ${response.status}`);
        if (result.schema_version !== report.schema_version || result.catalog_version !== report.catalog_version)
          throw new Error('Каталог изменился. Пересчитайте базовый сценарий.');
        if (run === revision.current) { setBranch({ key, report: result }); setFailure(null);
          onBranchRef.current?.({ input: draft, report: result }); }
      } catch (cause) {
        if (cause.name !== 'AbortError' && run === revision.current)
          setFailure({ key, message: cause.message });
      }
    }, 320);
    return () => { window.clearTimeout(timer); controller.abort(); revision.current += 1; };
  }, [changed, controls, input, key, report]);
  const patch = (field, value) => { onBranchRef.current?.(null);
    setControls((prior) => ({ ...prior, [field]: value })); };
  const reset = () => { setControls({ ...DEFAULT_WHAT_IF }); setBranch(null); setFailure(null); onBranchRef.current?.(null); };
  const base = whatIfSummary(report);
  const comparison = current ? whatIfSummary(current) : null;
  return <section className="what-if-panel" aria-label="Что если?">
    <h2>Что если?</h2><p>Временная ветка пересчитывается на сервере. Базовый отчёт, каталог и PDF остаются исходными; изменение объёма или скорости повторно запускает расчёт парка и маршрута.</p>
    <div className="what-if-fields">
      <Slider label="Цена робота" value={controls.pricePercent} onChange={(v) => patch('pricePercent', v)} unit="%" />
      <Slider label="ФОТ" value={controls.laborPercent} onChange={(v) => patch('laborPercent', v)} unit="%" />
      <Slider label="Скорость/выработка" value={controls.speedPercent} onChange={(v) => patch('speedPercent', v)} unit="%" />
      <Slider label="Сервис и поддержка" value={controls.servicePercent} onChange={(v) => patch('servicePercent', v)} unit="%" />
      <Slider label="Объём работ" value={controls.volumePercent} onChange={(v) => patch('volumePercent', v)} unit="%" />
      <Slider label="Ставка дисконтирования" value={controls.discountPoints}
        onChange={(v) => patch('discountPoints', v)} min={-10} max={10} unit=" п.п."
        base={`${number(Number(input.general.discount_rate) * 100, 2)}%`} />
      <Slider label="Доля реализуемого ФОТ" value={controls.laborSharePercent
        ?? Math.round(Number(input.general.realizable_labor_share) * 100)}
      onChange={(v) => patch('laborSharePercent', v)} min={0} max={100} unit="%" />
    </div>
    <details><summary>Дополнительно</summary><div className="what-if-fields">
      <Slider label="Расходы на интеграцию" value={controls.integrationPercent}
        onChange={(v) => patch('integrationPercent', v)} />
      <Slider label="Тариф RaaS" value={controls.rentPercent} onChange={(v) => patch('rentPercent', v)} />
      <Slider label="Запас парка" value={controls.reservePercent
        ?? Math.round(Number(input.general.fleet_reserve_share) * 100)}
      onChange={(v) => patch('reservePercent', v)} min={0} max={100} unit="%" />
      <label className="what-if-field"><span>Горизонт расчёта</span><select
        value={controls.horizonYears ?? Number(input.general.horizon_years)}
        onChange={(event) => patch('horizonYears', Number(event.target.value))}>
        {[5, 10].map((years) => <option key={years} value={years}>{years} лет</option>)}
      </select></label>
    </div></details>
    <button type="button" className="secondary-action" onClick={reset} disabled={!changed}>Сбросить «Что если?»</button>
    <div className="what-if-comparison"><Metrics title="Базовый сценарий" summary={base} horizon={report.general.horizon_years} />
      {comparison ? <Metrics title="Что если?" summary={comparison} horizon={current.general.horizon_years} baseline={base} />
        : <section className="what-if-column" aria-live="polite"><h3>Что если?</h3>
          <p>{!changed ? 'Выберите изменение, чтобы сравнить сценарии.' : error || 'Пересчитывается на сервере…'}</p></section>}</div>
  </section>;
}
