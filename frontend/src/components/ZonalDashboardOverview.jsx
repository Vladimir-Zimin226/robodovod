import { useState } from 'react';
import AppIcon from './AppIcon';
import RobCraftFrame from './RobCraftFrame';

const money = (value) => value == null ? '—' : Math.abs(value) >= 1e6
  ? `${(value / 1e6).toFixed(1)} млн ₽`
  : `${Math.round(value / 1e3)} тыс ₽`;

export default function ZonalDashboardOverview({ result }) {
  const [viewMode, setViewMode] = useState('target');
  const summary = result.combined;
  const recommendedZones = result.zones.filter((zone) => zone.status === 'RECOMMENDED');
  const best = recommendedZones.map((zone) => zone.recommendations.find((item) => item.is_best)).filter(Boolean);
  const readiness = best.length ? Math.round(best.reduce((sum, item) => sum + item.readiness_score, 0) / best.length) : null;
  const utilization = best.length ? best.reduce((sum, item) => sum + item.fleet_utilization, 0) / best.length : null;
  const baselineFte = result.zones.reduce((sum, zone) => sum + (zone.manual_baseline?.manual_fte || 0), 0);
  const baselineCost = result.zones.reduce((sum, zone) => sum + (zone.manual_baseline?.total_cost_annual || 0), 0);
  const visualizationZoneIds = new Set(result.scenario_spec?.fleet?.map((item) => item.zone_id) || []);

  return <section className="dashboard-overview" aria-label="Сводка зонального ТЭО">
    <div className="dashboard-title-row">
      <div><span className="eyebrow">ЗОНАЛЬНЫЙ РАСЧЁТ</span><h1>Единая сводка по объекту</h1><p>{summary.zones_count} зон · {summary.horizon_years} лет · ревизия {result.revision_id}</p></div>
      <span className={`status-pill ${recommendedZones.length ? 'success' : 'danger'}`}>{recommendedZones.length} из {summary.zones_count} зон рекомендованы</span>
    </div>
    {recommendedZones.length !== summary.zones_count && <div className="economics-empty" role="status"><AppIcon name="warning" /><div><strong>Не для всех зон назначен приемлемый парк</strong><p>Отвергнутые экономикой варианты не получают рекомендацию; технически допустимые могут показываться только как явно маркированная визуализация.</p></div></div>}
    <div className="dashboard-main-grid">
      <article className="visualization-card panel" id="visualization">
        <div className="visualization-toolbar"><div className="segmented-control" aria-label="Режим визуализации"><button className={viewMode === 'current' ? 'active' : ''} onClick={() => setViewMode('current')} aria-pressed={viewMode === 'current'}>Текущее состояние</button><button className={viewMode === 'target' ? 'active' : ''} onClick={() => setViewMode('target')} aria-pressed={viewMode === 'target'}>После внедрения</button></div><div className="broadcast-state"><span />{viewMode === 'target' ? 'МНОГОЗОННЫЙ ЭФИР' : 'BASELINE'}</div></div>
        <div className="scene-stage"><div className={viewMode === 'current' ? 'robcraft-layer is-hidden' : 'robcraft-layer'}><RobCraftFrame scenarioSpec={result.scenario_spec} compact /></div>{viewMode === 'current' && <div className="baseline-scene"><div className="baseline-grid" /><div className="baseline-flow"><span /><span /><span /></div><div className="baseline-copy"><span>ТЕКУЩИЙ ПРОЦЕСС</span><h3>Ручной baseline зон</h3><p>Отдельная 3D-модель текущего объекта не поступает из расчёта. Показаны только подтверждённые данные.</p></div><div className="baseline-metrics"><div><span>Персонал</span><strong>{baselineFte || '—'} FTE</strong></div><div><span>Стоимость/год</span><strong>{money(baselineCost)}</strong></div><div><span>Зон</span><strong>{summary.zones_count}</strong></div></div></div>}</div>
        <footer className="scene-footer"><strong>Репрезентативные сцены зон</strong><span>Без ложной единой физической модели здания</span></footer>
      </article>
      <aside className="insights-column">
        <article className="readiness-card panel"><h2>Готовность к внедрению</h2><div className="readiness-content"><div className={`readiness-ring ${readiness == null ? 'danger' : readiness >= 75 ? 'good' : 'caution'}`} style={{ '--score': readiness || 0 }}><strong>{readiness ?? '—'}</strong><span>среднее</span></div><ul><li className={recommendedZones.length ? 'ok' : 'bad'}><AppIcon name={recommendedZones.length ? 'check' : 'warning'} size={16} />{recommendedZones.length} зон с парком</li><li className={recommendedZones.length === summary.zones_count ? 'ok' : 'warn'}><AppIcon name={recommendedZones.length === summary.zones_count ? 'check' : 'warning'} size={16} />Экономика проверена по зонам</li><li className="warn"><AppIcon name="warning" size={16} />Нужно инженерное обследование</li></ul></div></article>
        <article className="kpi-panel panel"><div className="panel-heading"><h2>Ключевые показатели</h2><span>Сводка backend</span></div><div className="kpi-grid"><div className="kpi amber"><span>CAPEX</span><strong>{money(summary.total_capex)}</strong></div><div className="kpi lime"><span>Окупаемость</span><strong>{summary.combined_payback_years > summary.horizon_years ? `> ${summary.horizon_years} лет` : `${summary.combined_payback_years} года`}</strong></div><div className="kpi cyan"><span>Парк</span><strong>{summary.total_robots} ед.</strong></div><div className="kpi violet"><span>NPV</span><strong>{money(summary.total_npv)}</strong></div><div className="kpi cyan wide"><span>Экономия в год</span><strong>{money(summary.total_savings_annual)}</strong></div></div><button className="primary-cta" onClick={() => document.getElementById('zone-details')?.scrollIntoView({ behavior: 'smooth' })}>Открыть зоны <AppIcon name="arrow" /></button></article>
      </aside>
    </div>
    <div className="analytics-grid" id="scenarios">
      <article className="scenario-card panel"><div className="panel-heading"><h2>Статус зон</h2><span>{recommendedZones.length}/{summary.zones_count}</span></div>{result.zones.slice(0, 4).map((zone) => <div key={zone.zone_id} className={`zone-status-row ${zone.status === 'RECOMMENDED' ? 'ok' : 'bad'}`}><span><strong>{zone.zone_name}</strong><small>{zone.status === 'RECOMMENDED' ? `${zone.zone_robots} роботов` : zone.status_message}</small></span><b>{zone.status === 'RECOMMENDED' ? money(zone.zone_capex) : visualizationZoneIds.has(zone.zone_id) ? 'Только визуализация' : 'Без парка'}</b></div>)}</article>
      <article className="economic-profile panel"><div className="panel-heading"><h2>Экономический эффект</h2><span>{summary.horizon_years} лет</span></div><div className="economic-summary zonal-summary"><span>OPEX/год <b>{money(summary.total_opex_annual)}</b></span><span>Эффект/год <b>{money(summary.total_net_annual)}</b></span><span>TCO <b>{money(summary.total_tco)}</b></span><span>NPV <b className={summary.total_npv >= 0 ? 'positive' : 'negative'}>{money(summary.total_npv)}</b></span></div><p className="data-note">Warehouse fixed CAPEX учтён backend один раз: {money(summary.warehouse_fixed_rub)}.</p></article>
      <article className="resources-card panel"><div className="panel-heading"><h2>Ресурсы объекта</h2><span>Сводка зон</span></div><div className="resource-row"><div><span>Персонал</span><b>{baselineFte || '—'} → {baselineFte ? Math.max(0, baselineFte - summary.total_released) : '—'} FTE</b></div><div className="bar-track"><span style={{ width: baselineFte ? `${Math.max(4, (1 - summary.total_released / baselineFte) * 100)}%` : '4%' }} /></div></div><div className="resource-row"><div><span>Средняя загрузка парка</span><b>{utilization == null ? '—' : `${Math.round(utilization * 100)}%`}</b></div><div className="bar-track"><span style={{ width: utilization == null ? '4%' : `${utilization * 100}%` }} /></div></div></article>
      <article className="impact-card panel"><div className="panel-heading"><h2>Граница модели</h2><span>Важно</span></div><div className="impact-value"><AppIcon name="warning" /><div><span>Геометрия</span><strong>Сцены зон независимы; общие коридоры не моделируются</strong></div></div><p>Межзональные очереди и конфликты не включены в расчёт.</p></article>
    </div>
  </section>;
}
