import { simulationFlagLabel, simulationStatusLabel } from '../presentation.js';

const ru = (value, digits = 2) => value == null ? 'Нужны данные'
  : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: digits }).format(Number(value));
const rub = (value) => value == null ? 'Нужны данные' : `${ru(value)} ₽`;
const percent = (value) => value == null ? 'Нет данных' : `${ru(value)}%`;

function Cashflow({ name, rows }) {
  if (!rows.length) return <p>{name}: для графика нужны цена или тариф.</p>;
  const bound = Math.max(1, ...rows.map((row) => Math.abs(Number(row.cumulative_rub))));
  return <div className="investment-chart"><h4>{name}</h4><div role="img" aria-label={`Накопленный денежный поток: ${name}`}>
    {rows.map((row) => <div key={row.year} className="investment-chart-row">
      <span>Год {row.year}</span><div className="investment-chart-track"><i style={{ width: `${Math.abs(Number(row.cumulative_rub)) / bound * 100}%`,
        background: Number(row.cumulative_rub) < 0 ? '#aa534c' : '#3a9d69' }} /></div>
      <strong>{rub(row.cumulative_rub)}</strong>
    </div>)}
  </div></div>;
}

function Waterfall({ rows }) {
  if (!rows.length) return <p>Для waterfall нужны цена и ФОТ.</p>;
  const values = rows.flatMap((row) => [Number(row.start_rub), Number(row.end_rub), 0]);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = Math.max(1, maximum - minimum);
  return <div className="investment-waterfall" role="img" aria-label="Ступени дисконтированного NPV покупки">
    {rows.map((row) => {
      const start = Number(row.start_rub);
      const end = Number(row.end_rub);
      return <div key={row.label} className="investment-chart-row">
        <span>{row.label}</span><div className="investment-chart-track">
          <i style={{ marginLeft: `${(Math.min(start, end) - minimum) / span * 100}%`,
            width: `${Math.max(1, Math.abs(end - start) / span * 100)}%`,
            background: end >= start ? '#3a9d69' : '#aa534c' }} /></div>
        <strong>{rub(row.amount_rub)}</strong>
      </div>;
    })}
  </div>;
}

export default function InvestmentReport({ view, comparison }) {
  if (view?.schema_version !== 'role-report-view-v1') return null;
  return <main className="investment-report" aria-label="Инвестиционный отчёт">
    <header><p>РОБОДОВОД · ИНВЕСТИЦИОННАЯ ОЦЕНКА</p><h1>{view.object}</h1>
      <p className="investment-verdict">{view.executive_conclusion}</p>
      <p>{view.evidence_status}</p><small>Дата UTC: {view.date_utc} · каталог {view.catalog_version} · расчёт {view.calculation_version}</small></header>
    <section className="investment-kpis" aria-label="Ключевые показатели покупки">
      {[
        ['Парк', ru(view.fleet)],
        ['Эквивалент ставок', ru(view.fte_equivalent)],
        ['Капвложения', rub(view.economics.purchase.capex_rub)],
        ['Эффект за год', rub(view.economics.purchase.annual_net_rub)],
        [`NPV · ${view.active_horizon_years} лет`, rub(view.economics.purchase.npv_rub)],
        ['Окупаемость', view.economics.purchase.payback_years == null ? 'Не достигается или нужны данные' : `${ru(view.economics.purchase.payback_years)} лет`],
      ].map(([label, value]) => <div key={label}><span>{label}</span><strong title={value}>{value}</strong></div>)}
    </section>
    <section><h2>Управленческий вывод</h2><p>{view.executive_conclusion}</p>
      <p>Парк: {view.fleet} · эквивалент ставок: {ru(view.fte_equivalent)} · горизонт: {view.active_horizon_years} лет</p></section>
    <section><h2>Работы, люди и модели</h2><div className="investment-table-scroll"><table className="investment-works-table"><thead><tr>
      <th>Работа</th><th>Люди</th><th>Объём/сутки</th><th>Модель и парк</th><th>Основание</th>
    </tr></thead><tbody>{view.works.map((work, index) => <tr key={`${work.role}-${index}`}>
      <td data-label="Работа"><strong>{work.role}</strong><small>{work.task}</small></td><td data-label="Люди">{ru(work.headcount)}<small>{rub(work.salary_rub_month)}/мес.</small></td>
      <td data-label="Объём/сутки">{ru(work.volume_per_day)} {work.unit}</td><td data-label="Модель и парк">{work.model || 'Сценарный тип / не выбрана'}<small>Парк: {work.fleet}; ТТХ: {work.physical_fit || 'не подтверждены'}</small></td>
      <td data-label="Основание">{work.rate_source || 'Неизвестно'}<small>Позиция: {work.position_id || 'не выбрана'} · {work.price_source || 'Цена неизвестна'} · {work.evidence_ref || 'сценарное допущение'}</small></td>
    </tr>)}</tbody></table></div></section>
    <section><h2>Симуляция и ограничения маршрута</h2>
      {view.simulations.length ? view.simulations.map((sim, index) => <p key={`${sim.role}-${index}`}>
        {sim.role}: маршрут {simulationStatusLabel(sim.status)}; цикл {ru(sim.cycle_s)} с; загруженный ход {ru(sim.distance_loaded_m)} м;
        ожидание {ru(sim.time_wait_s)} с; парк после симуляции {sim.fleet_required ?? 'не рассчитан'}.
        {sim.shared_lane && ` Узкий участок: ожидание ${ru(sim.shared_lane.mean_wait_s)} с.`}
        {sim.flags.length > 0 && ` Ограничения: ${sim.flags.map(simulationFlagLabel).join('; ')}.`}</p>)
        : <p>Маршрутная симуляция не включена; выработка остаётся сценарной.</p>}</section>
    <section><h2>Покупка и аренда</h2><div className="investment-table-scroll"><table><thead><tr>
      <th>Вариант</th><th>CAPEX</th><th>Чистый эффект/год</th><th>NPV</th><th>ROI</th><th>Окупаемость</th>
    </tr></thead><tbody>{[['purchase', 'Покупка'], ['raas', 'Аренда']].map(([key, label]) => {
      const money = view.economics[key];
      return <tr key={key}><th>{label}</th><td>{rub(money.capex_rub)}</td><td>{rub(money.annual_net_rub)}</td>
        <td>{rub(money.npv_rub)}</td><td>{percent(money.roi_percent)}</td>
        <td>{key === 'purchase' ? money.payback_years == null ? 'Не достигается или нужны данные' : `${ru(money.payback_years)} лет` : 'Не применяется'}</td></tr>;
    })}</tbody></table></div>
      <p>При аренде разовые вложения до старта: {rub(view.economics.raas.capex_rub)}. Аренда и сопутствующие расходы за первый год: {rub(view.economics.raas.annual_operating_cost_rub)}. Год 0 на графике — до начала эксплуатации; платежи года 1 учтены в чистом годовом эффекте.</p>
      <h3>Горизонты 5 и 10 лет</h3><div className="investment-table-scroll"><table><thead><tr>
      <th>Вариант</th><th>Горизонт</th><th>NPV</th><th>ROI</th>
    </tr></thead><tbody>{[['purchase', 'Покупка'], ['raas', 'Аренда']].flatMap(([key, label]) =>
      view.economics[key].horizons.map((row) => <tr key={`${key}-${row.years}`}><th>{label}</th><td>{row.years} лет</td>
        <td>{rub(row.npv_rub)}</td><td>{percent(row.roi_percent)}</td></tr>))}</tbody></table></div>
      <h3>Накопленный денежный поток, годы 0–10</h3><div className="investment-chart-grid">
        <Cashflow name="Покупка" rows={view.economics.purchase.cashflows} />
        <Cashflow name="Аренда" rows={view.economics.raas.cashflows} /></div>
      <h3>Ступени дисконтированного NPV покупки</h3><Waterfall rows={view.waterfall} />
      <h3>Чувствительность к реализуемой доле ФОТ</h3><div className="investment-table-scroll"><table><thead><tr>
        <th>Доля</th><th>NPV покупки</th><th>NPV аренды</th><th>Горизонт</th>
      </tr></thead><tbody>{view.sensitivity.map((row) => <tr key={row.labor_share}>
        <td>{ru(Number(row.labor_share) * 100, 0)}%</td><td>{rub(row.purchase_npv_rub)}</td>
        <td>{rub(row.raas_npv_rub)}</td><td>{view.active_horizon_years} лет</td>
      </tr>)}</tbody></table></div></section>
    <section><h2>Сценарии и «Что если?»</h2>{view.conditional && <p>Условный сценарий: парк {view.conditional.fleet};
      NPV покупки {rub(view.conditional.purchase_npv_rub)}. {view.conditional.warning}</p>}
      {comparison?.schema_version === 'role-report-view-v1' ? <div className="investment-table-scroll"><table><thead><tr>
        <th>Показатель</th><th>База</th><th>Что если?</th>
      </tr></thead><tbody>{[['fleet', 'Парк', (item) => item.fleet],
        ['purchase-capex', 'Покупка · CAPEX', (item) => rub(item.economics.purchase.capex_rub)],
        ['purchase-npv', 'Покупка · NPV', (item) => rub(item.economics.purchase.npv_rub)],
        ['raas-npv', 'Аренда · NPV', (item) => rub(item.economics.raas.npv_rub)]].map(([key, label, pick]) =>
        <tr key={key}><th>{label}</th><td>{pick(view)}</td><td>{pick(comparison)}</td></tr>)}</tbody></table></div>
        : <p>{view.what_if}</p>}</section>
    <section><h2>Риски, источники и допущения</h2><ul>{view.risks.map((risk, index) => <li key={index}>{risk}</li>)}</ul>
      <p>Выработка, цены и основание для каждой работы указаны в таблице. Каталог: {view.catalog_version}; версия отчёта: {view.schema_version}.</p>
      <p>Доступность: {view.assumptions.robot_availability}; запас парка: {view.assumptions.fleet_reserve_share};
        реализуемая доля ФОТ: {view.assumptions.realizable_labor_share}; интеграция: {view.assumptions.integration_share};
        сервис: {view.assumptions.annual_service_share}; дисконтирование: {view.assumptions.discount_rate}.</p></section>
  </main>;
}
