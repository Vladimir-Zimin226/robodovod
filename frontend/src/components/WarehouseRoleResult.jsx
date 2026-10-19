import AppIcon from './AppIcon';
import './WarehouseRoleWorkspace.css';

const money = (value) => value == null ? 'Не рассчитано' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(value))} ₽`;
const count = (value) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value));

export default function WarehouseRoleResult({ report, focus = 'all', onEdit }) {
  if (!report || report.schema_version !== 'warehouse-role-analysis-v1') return null;
  const showRobots = focus !== 'money';
  const showMoney = focus !== 'robots';
  return <main className="wr-workspace" aria-label="Результат расчёта склада по ролям">
    <header className="wr-hero"><div><p className="wr-kicker">СКЛАД · РАСЧЁТ ПО РОЛЯМ</p>
      <h1>{focus === 'robots' ? 'Роботы для ваших сотрудников' : focus === 'money' ? 'Экономика всего склада' : 'Результат по складу'}</h1>
      <p>Рассмотрено {report.catalog_positions_checked} позиций каталога для каждой из {report.roles.length} выбранных ролей. Версия каталога: {report.catalog_version}.</p></div>
      <div className="wr-hero-mark"><AppIcon name="chart" size={52} /><span>ЕДИНЫЙ<br />РЕЗУЛЬТАТ</span></div></header>
    {showRobots && <section className="wr-panel"><div className="wr-section-heading"><span className="wr-section-number">01</span><div><h2>Подбор по каждой роли</h2>
      <p>Выбранные модели и потребный парк. Остальные варианты доступны при редактировании расчёта.</p></div></div>
      <div className="wr-role-grid">{report.roles.map((role) => {
        const selected = role.candidates.find((row) => row.position_id === role.selected_position_id);
        return <article key={role.role_code} className="wr-role-card selected"><div className="wr-role-toggle">
          <span className="wr-role-icon"><AppIcon name={role.role_code} size={26} /></span>
          <span className="wr-role-title"><strong>{role.label}</strong><small>{role.candidates.length} вариантов в каталоге</small></span></div>
          <div className="wr-role-body">{selected ? <><strong>{selected.name}</strong><p className="wr-disclaimer">
            {selected.fleet} роботов · {count(selected.fte_equivalent)} ставки в сценарии · {selected.rate_source === 'SCENARIO_ASSUMPTION' ? 'выработка по допущению' : 'выработка из данных'}</p>
            {selected.work_scope === 'DELIVERY_TO_PICKING_STATION' && <p className="wr-disclaimer">Робот подвозит товар; фактический отбор выполняет человек. Эффект относится только к времени на подвоз.</p>}
            {selected.work_scope === 'PALLET_TRANSPORT_ONLY' && <p className="wr-disclaimer">Робот перевозит паллеты; погрузка и разгрузка остаются ручными. Эффект относится только к перевозке.</p>}
            {selected.maturity_status === 'PILOTING' && <p className="wr-disclaimer">Модель на стадии пилотирования; доступность поставки требует проверки.</p>}
            {selected.status === 'RESEARCH_ONLY' && <p className="wr-disclaimer">Исследовательская модель: закупочная готовность не подтверждена.</p>}</>
            : <p className="wr-disclaimer">Робот пока не выбран. Рассмотрено {role.catalog_checked} позиций.</p>}</div></article>;
      })}</div></section>}
    {showMoney && <section className="wr-portfolio"><div className="wr-section-heading"><span className="wr-section-number">02</span><div><h2>Сводный сценарий</h2>
      <p>Суммы относятся к выбранным назначениям роботов; оценка по каждой роли остаётся видимой отдельно.</p></div></div>
      <div className="wr-portfolio-grid"><div><span>Ролей с выбранным роботом</span><strong>{report.portfolio.selected_roles}/{report.roles.length}</strong></div>
        <div><span>Парк</span><strong>{report.portfolio.selected_robot_allocations}</strong></div>
        <div><span>Ставки в сценарии*</span><strong>{count(report.portfolio.fte_equivalent)}</strong></div>
        <div><span>Потенциал ФОТ в год*</span><strong>{money(report.portfolio.annual_labor_potential_rub)}</strong></div>
        <div><span>Капвложения</span><strong>{money(report.portfolio.capex_rub)}</strong></div>
        <div><span>NPV сценария</span><strong>{money(report.portfolio.npv_rub)}</strong></div></div>
      <p className="wr-disclaimer">* Оценка при сценарной доле реализации. Деньги остаются частичными, если нет цены хотя бы одного выбранного робота.</p></section>}
    <details className="wr-limitations"><summary>Что нужно проверить перед решением о закупке</summary>
      <ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      {report.general && <p>Допущения: доступность робота {count(Number(report.general.robot_availability) * 100)}%, резерв парка {count(Number(report.general.fleet_reserve_share) * 100)}%,
        перевод времени в ставки {count(Number(report.general.realizable_labor_share) * 100)}%, внедрение {count(Number(report.general.integration_share) * 100)}%,
        сервис {count(Number(report.general.annual_service_share) * 100)}% от цены в год, ставка дисконтирования {count(Number(report.general.discount_rate) * 100)}%, горизонт {report.general.horizon_years} лет.</p>}</details>
    {onEdit && <div className="wr-actions"><button type="button" className="wr-primary" onClick={onEdit}>Изменить роли и пересчитать</button></div>}
  </main>;
}
