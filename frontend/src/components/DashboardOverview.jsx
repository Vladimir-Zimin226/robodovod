import { useMemo, useState } from 'react';
import { getDashboardModel, SCENARIO_LABELS } from '../dashboardModel';
import AppIcon from './AppIcon';
import RobCraftFrame from './RobCraftFrame';

const money = (value) => {
  if (value == null || Number.isNaN(value)) return '—';
  const absolute = Math.abs(value);
  if (absolute >= 1e6) return `${(value / 1e6).toFixed(1)} млн ₽`;
  return `${Math.round(value / 1e3)} тыс ₽`;
};

const years = (value, horizon) => value == null ? '—' : value > horizon ? `> ${horizon} лет` : `${value} года`;
const pct = (value) => value == null ? '—' : `${Math.round(value * 100)}%`;

export default function DashboardOverview({ result, userInput }) {
  const [scenario, setScenario] = useState('base');
  const [viewMode, setViewMode] = useState('target');
  const model = useMemo(() => getDashboardModel(result, userInput, scenario), [result, userInput, scenario]);
  const horizon = model.economics?.horizon_years || userInput?.horizon_years || 5;
  const readinessReport = result.readiness_report;
  const readiness = readinessReport?.score ?? model.readiness;
  const readinessTone = readiness == null ? 'muted' : readiness >= 75 ? 'good' : readiness >= 50 ? 'caution' : 'danger';
  const scenarioChoices = model.recommended?.scenarios || [];
  const visualizedFleet = result.scenario_spec?.fleet?.[0];
  const visualizedRecommendation = result.recommendations?.find((item) => item.robot_id === visualizedFleet?.equipment_model_id);
  const technicalOption = model.recommended || visualizedRecommendation;

  return (
    <section className="dashboard-overview" aria-label="Сводка предварительного ТЭО">
      <div className="dashboard-title-row">
        <div>
          <span className="eyebrow">ПРЕДВАРИТЕЛЬНОЕ ТЭО</span>
          <h1>{model.processType ? processName(model.processType) : 'Сценарий роботизации'}</h1>
          <p>{model.facilityArea ? `${formatNumber(model.facilityArea)} м²` : 'Площадь объекта уточняется'}</p><details><summary>Технические подробности</summary>{model.revisionId ? `Версия ввода: ${model.revisionId}` : 'Версия ввода формируется'}</details>
        </div>
        <span className={`status-pill ${model.hasAcceptableRecommendation ? 'success' : 'danger'}`}>
          {model.hasAcceptableRecommendation ? 'Экономика приемлема' : 'Нет приемлемой экономики'}
        </span>
      </div>

      {!model.hasAcceptableRecommendation && (
        <div className="economics-empty" role="status">
          <AppIcon name="warning" />
          <div><strong>Подходящий экономический сценарий пока не найден</strong><p>{result.warnings?.[0] || 'Технически допустимые варианты сохранены для сравнения, но ни один не назначен рекомендованным.'}</p></div>
        </div>
      )}

      <div className="dashboard-main-grid">
        <article className="visualization-card panel" id="visualization">
          <div className="visualization-toolbar">
            <div className="segmented-control" aria-label="Режим визуализации">
              <button className={viewMode === 'current' ? 'active' : ''} onClick={() => setViewMode('current')} aria-pressed={viewMode === 'current'}>Текущее состояние</button>
              <button className={viewMode === 'target' ? 'active' : ''} onClick={() => setViewMode('target')} aria-pressed={viewMode === 'target'}>После внедрения</button>
            </div>
            <div className="broadcast-state"><span />{viewMode === 'target' ? 'СЦЕНАРНЫЙ ЭФИР' : 'BASELINE'}</div>
          </div>
          <div className="scene-stage">
            <div className={viewMode === 'current' ? 'robcraft-layer is-hidden' : 'robcraft-layer'}>
              <RobCraftFrame scenarioSpec={result.scenario_spec} compact />
            </div>
            {viewMode === 'current' && <BaselineScene baseline={model.baseline} />}
          </div>
          <footer className="scene-footer">
            <strong>{model.recommended ? `Сценарий: ${model.recommended.robot_name}` : visualizedRecommendation ? `Визуализация: ${visualizedRecommendation.robot_name} · не рекомендация` : 'Сценарий: без назначенного парка'}</strong>
            <span>{viewMode === 'target' ? 'Интерактивная сценарная симуляция' : 'Расчётный baseline без 3D-подмены'}</span>
          </footer>
        </article>

        <aside className="insights-column" aria-label="Ключевые показатели">
          <article className="readiness-card panel">
            <h2>Готовность к внедрению</h2>
            <div className="readiness-content">
              <div className={`readiness-ring ${readinessTone}`} style={{ '--score': readiness || 0 }}><strong>{readiness ?? '—'}</strong><span>из 100</span></div>
              <ul>
                {readinessReport ? <>
                  <Check ok={readinessReport.overall_status === 'READY'} warning={readinessReport.overall_status === 'NEEDS_VALIDATION'}>{readinessStatus(readinessReport.overall_status)}</Check>
                  <Check ok={!readinessReport.blockers.length}>{readinessReport.blockers.length ? `Блокеров: ${readinessReport.blockers.length}` : 'Критических FAIL нет'}</Check>
                  <Check ok={readinessReport.confidence === 'HIGH'} warning>{`Доверие: ${confidenceLabel(readinessReport.confidence)}`}</Check>
                  <Check ok={false} warning>{architectureLabel(readinessReport.architecture_candidates?.[0]?.architecture_id)}</Check>
                </> : <>
                  <Check ok={technicalOption?.technical_status === 'ELIGIBLE'}>Технически реализуемо</Check>
                  <Check ok={(model.dataCompleteness || 0) >= 75}>Данные достаточны: {model.dataCompleteness ?? '—'}%</Check>
                </>}
              </ul>
            </div>
          </article>
          <article className="kpi-panel panel" id="economics">
            <div className="panel-heading"><h2>Ключевые показатели</h2><span>{SCENARIO_LABELS[scenario]} сценарий</span></div>
            {model.economics ? (
              <div className="kpi-grid">
                <Kpi tone="amber" label="CAPEX" value={money(model.economics.capex)} />
                <Kpi tone="lime" label="Окупаемость" value={years(model.economics.payback_years, horizon)} />
                <Kpi tone="cyan" label={`ROI (${horizon} лет)`} value={`${Math.round(model.economics.roi_pct)}%`} />
                <Kpi tone="violet" label="NPV" value={money(model.economics.npv)} />
                <Kpi tone="cyan" wide label="Экономия в год" value={money(model.economics.savings_annual)} />
              </div>
            ) : <p className="panel-empty">Показатели рекомендации отсутствуют. Сравните технически допустимые варианты ниже.</p>}
            <button className="primary-cta" onClick={() => document.getElementById('scenarios')?.scrollIntoView({ behavior: 'smooth' })}>Посмотреть варианты <AppIcon name="arrow" /></button>
          </article>
        </aside>
      </div>

      {readinessReport && <ReadinessDetails report={readinessReport} />}

      <div className="analytics-grid">
        <article className="scenario-card panel" id="scenarios">
          <div className="panel-heading"><h2>Сравнение сценариев</h2><span>Экономические допущения</span></div>
          {scenarioChoices.length ? scenarioChoices.map((item) => (
            <button key={item.scenario} className={scenario === item.scenario ? 'scenario-row active' : 'scenario-row'} onClick={() => setScenario(item.scenario)} aria-pressed={scenario === item.scenario}>
              <span><strong>{SCENARIO_LABELS[item.scenario]}</strong><small>{item.quantity} ед. · загрузка {pct(item.utilization)}</small></span>
              <b>{years(item.payback_years, item.horizon_years)}</b>
            </button>
          )) : <p className="panel-empty">Рекомендованный сценарий не назначен.</p>}
        </article>

        <article className="economic-profile panel">
          <div className="panel-heading"><h2>Экономический эффект</h2><span>{horizon} лет</span></div>
          {model.economics ? <>
            <div className="economic-bars">
              <EconomicBar label="TCO" value={model.economics.tco} max={Math.max(model.economics.tco, model.economics.capex)} tone="gray" />
              <EconomicBar label="CAPEX" value={model.economics.capex} max={Math.max(model.economics.tco, model.economics.capex)} tone="lime" />
            </div>
            <div className="economic-summary"><span>NPV <b className={model.economics.npv >= 0 ? 'positive' : 'negative'}>{money(model.economics.npv)}</b></span><span>Чистый эффект/год <b>{money(model.economics.net_annual)}</b></span></div>
            <p className="data-note">Показаны готовые показатели backend; временной cash-flow ряд не моделируется во frontend.</p>
          </> : <p className="panel-empty">Экономический профиль не сформирован.</p>}
        </article>

        <article className="resources-card panel">
          <div className="panel-heading"><h2>Использование ресурсов</h2><span>Целевой сценарий</span></div>
          <ResourceRow label="Персонал" current={model.fteTotal} after={model.fteRetained} />
          <ResourceRow label="Высвобождение" text={model.fteReleased == null ? '—' : `${model.fteReleased} FTE`} ratio={model.fteTotal ? model.fteReleased / model.fteTotal : null} />
          <ResourceRow label="Парк роботов" text={model.fleetSize ? `${model.fleetSize} ед.${model.hasAcceptableRecommendation ? '' : ' · только визуализация'}` : 'не назначен'} ratio={model.fleetUtilization} />
        </article>

        <article className="impact-card panel">
          <div className="panel-heading"><h2>Контекст решения</h2><span>Без вымышленных метрик</span></div>
          <div className="impact-value"><AppIcon name={model.warning ? 'warning' : 'check'} /><div><span>{model.warning ? 'Ключевое условие' : 'Качество данных'}</span><strong>{model.warning || model.dataQualityLevel || 'Не определено'}</strong></div></div>
          <div className="confidence-line"><span>Confidence цены</span><b>{model.confidence == null ? 'не задан' : `${Math.round(model.confidence * 100)}%`}</b></div>
          <p>Результат является предварительной оценкой и требует подтверждения интегратором.</p>
        </article>
      </div>
    </section>
  );
}

function BaselineScene({ baseline }) {
  return <div className="baseline-scene" role="img" aria-label="Текущее состояние процесса по расчётному baseline">
    <div className="baseline-grid" />
    <div className="baseline-flow"><span /><span /><span /></div>
    <div className="baseline-copy"><span>ТЕКУЩИЙ ПРОЦЕСС</span><h3>Ручной baseline</h3><p>Отдельная 3D-сцена текущего состояния не поступает из расчёта. Ниже показаны только подтверждённые параметры.</p></div>
    <div className="baseline-metrics"><div><span>Персонал</span><strong>{baseline?.manual_fte ?? '—'} FTE</strong></div><div><span>Техника</span><strong>{baseline?.forklifts ? `${baseline.forklifts} ед.` : '—'}</strong></div><div><span>Стоимость/год</span><strong>{money(baseline?.total_cost_annual)}</strong></div></div>
  </div>;
}

function Check({ ok, warning = false, children }) { return <li className={ok ? 'ok' : warning ? 'warn' : 'bad'}><AppIcon name={ok ? 'check' : 'warning'} size={16} />{children}</li>; }
function Kpi({ tone, label, value, wide = false }) { return <div className={`kpi ${tone} ${wide ? 'wide' : ''}`}><span>{label}</span><strong>{value}</strong></div>; }
function EconomicBar({ label, value, max, tone }) { const width = max > 0 ? Math.max(3, Math.min(100, value / max * 100)) : 0; return <div className="economic-bar"><div><span>{label}</span><b>{money(value)}</b></div><div className="bar-track"><span className={tone} style={{ width: `${width}%` }} /></div></div>; }
function ResourceRow({ label, current, after, text, ratio }) { const resolved = ratio ?? (current ? Math.max(0, Math.min(1, after / current)) : 0); return <div className="resource-row"><div><span>{label}</span><b>{text || (current == null || after == null ? '—' : `${current} → ${after} FTE`)}</b></div><div className="bar-track"><span style={{ width: `${Math.max(4, Math.min(100, resolved * 100))}%` }} /></div></div>; }
function ReadinessDetails({ report }) {
  return <section className="readiness-details panel" aria-label="Детали готовности">
    <div className="panel-heading"><h2>Готовность и архитектура</h2><span>{readinessStatus(report.overall_status)} · {report.rules_version}</span></div>
    <div className="readiness-dimensions">{report.dimensions.map((dimension) => <div key={dimension.code} className={`readiness-dimension ${dimension.status.toLowerCase()}`}><span>{dimension.label}</span><strong>{dimension.score}/100</strong><small>{statusLabel(dimension.status)}</small></div>)}</div>
    <div className="readiness-detail-grid">
      <div><h3>Предлагаемая архитектура</h3><strong>{architectureLabel(report.architecture_candidates?.[0]?.architecture_id)}</strong><p>Выбор класса решения выполнен до выбора конкретной модели.</p></div>
      <div><h3>Что нужно подтвердить</h3>{report.preconditions.length ? <ul>{report.preconditions.slice(0, 5).map((item) => <li key={item}>{item}</li>)}</ul> : <p>Критических предусловий нет.</p>}</div>
    </div>
  </section>;
}
function readinessStatus(value) { return ({ READY: 'Готов к подбору', NEEDS_VALIDATION: 'Нужна проверка', NOT_READY: 'Не готов' })[value] || 'Не определено'; }
function confidenceLabel(value) { return ({ HIGH: 'высокое', MEDIUM: 'среднее', LOW: 'низкое' })[value] || 'не опредено'; }
function statusLabel(value) { return ({ PASS: 'подтверждено', FAIL: 'блокер', UNKNOWN: 'нет данных', ASSUMED: 'допущение' })[value] || value; }
function architectureLabel(value) { return ({ PALLET_TRANSPORT_AMR: 'AMR для паллетной логистики', FIXED_PATH_AGV: 'AGV с фиксированными маршрутами', AUTONOMOUS_FORKLIFT: 'Автономный погрузчик', TUGGER_TRAIN: 'Автономный тягач', PARTIAL_AUTOMATION: 'Частичная автоматизация', AUTONOMOUS_CLEANING: 'Автономная уборка', INDOOR_DELIVERY_AMR: 'AMR для внутренней доставки', NOT_READY: 'Архитектура не определена' })[value] || 'Архитектура не определена'; }
function processName(value) { return ({ transport: 'Внутренняя логистика', palletizing: 'Паллетизация', cleaning: 'Автономная уборка', delivery: 'Сервисная доставка' })[value] || 'Сценарий роботизации'; }
function formatNumber(value) { return new Intl.NumberFormat('ru-RU').format(value); }
