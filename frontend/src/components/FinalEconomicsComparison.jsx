import { useState } from 'react';
import { humanizePresentation, presentationValue } from '../presentation';

const METRICS = [
  ['capex', 'CAPEX'], ['opex_year_1', 'Затраты за год 1'],
  ['opex_change_year_1', 'Изменение затрат за год 1'], ['fot_year_1', 'ФОТ за год 1'],
  ['effect_year_1', 'Эффект за год 1'], ['effect_total', 'Эффект за горизонт'],
  ['net_benefit', 'Чистый эффект после вложений'], ['simple_payback', 'Простой срок окупаемости'],
  ['roi', 'ROI на инвестиции'], ['tco', 'TCO за горизонт'],
  ['npv', 'NPV'], ['discounted_payback', 'Дисконтированный срок окупаемости'],
];
const NAMES = { BASELINE: 'Без роботов', PURCHASE: 'Покупка', RAAS: 'Услуга RaaS' };
const UNCERTAINTY = { BASE: 'Базовый', PESSIMISTIC: 'Пессимистичный', OPTIMISTIC: 'Оптимистичный' };
const PARAMETERS = {
  EQUIPMENT_PRICE: 'Цена робота', RAAS_TARIFF: 'Тариф услуги',
  OPERATION_VOLUME: 'Объём работ', ROLE_SALARY: 'Зарплата роли',
  MANUAL_PRODUCTIVITY: 'Ручная выработка',
};
const amount = (raw, unit) => {
  if (raw == null || raw === '') return 'нет данных';
  return presentationValue('', raw, unit);
};
const value = (metric) => metric?.status === 'COMPLETE' ? amount(metric.value, metric.unit)
  : metric?.status === 'N_A' ? 'Не применяется'
    : metric?.status === 'NOT_REACHED' ? 'Не достигнут за горизонт'
      : 'Не сохранено в этой версии';

export default function FinalEconomicsComparison({ comparison }) {
  const [selected, setSelected] = useState('scenario.purchase.base');
  if (!comparison) return <section className="commercial-details" aria-label="Полное сравнение экономики">
    <h2>Без роботов, покупка и аренда</h2><p>Полная таблица показателей не сохранена в этой версии. Для неё создайте новый расчёт; этот результат остаётся воспроизводимым.</p>
  </section>;
  const baseRows = [comparison.baseline, ...comparison.scenarios.filter((item) => item.uncertainty === 'BASE')];
  const active = [comparison.baseline, ...comparison.scenarios].find((item) => item.scenario_id === selected) || baseRows[1];
  const variants = comparison.sensitivity?.by_scenario?.[active.scenario_id] || [];
  return <section className="commercial-details" aria-label="Полное сравнение экономики">
    <div className="commercial-section-title"><div><span>05</span><h2>Без роботов, покупка и услуга</h2></div><p>Горизонт {comparison.horizon_years} лет · суммы в рублях</p></div>
    <div className="commercial-table-wrap"><table><thead><tr><th>Показатель</th>{baseRows.map((item) => <th key={item.scenario_id}>{NAMES[item.acquisition]}</th>)}</tr></thead>
      <tbody>{METRICS.map(([key, label]) => <tr key={key}><th>{label}</th>{baseRows.map((item) => {
        const metric = item.metrics[key];
        return <td key={item.scenario_id}>{value(metric)}<small className="block">{humanizePresentation(metric?.basis || 'Источник не сохранён')}</small></td>;
      })}</tr>)}</tbody></table></div>
    <p>ROI имеет базу вложений CAPEX; при нулевом CAPEX он не определён. TCO показывает затраты за горизонт, NPV — дисконтированный эффект; эти показатели имеют разные базы.</p>
    <div className="commercial-table-wrap"><table><thead><tr><th>Год</th>{baseRows.map((item) => <th key={item.scenario_id}>{NAMES[item.acquisition]}</th>)}</tr></thead><tbody>
      {baseRows[0].annual_cashflows.map((flow) => <tr key={flow.year}><th>{flow.year}</th>{baseRows.map((item) => <td key={item.scenario_id}>{amount(item.annual_cashflows.find((row) => row.year === flow.year)?.scenario, 'RUB')}</td>)}</tr>)}
    </tbody></table></div>
    <h3>Разовые вложения по статьям</h3>
    <div className="commercial-table-wrap"><table><thead><tr><th>Вариант</th><th>Статья</th><th>Сумма</th><th>Основание</th></tr></thead><tbody>
      {baseRows.flatMap((item) => item.capital_lines.map((line, index) => <tr key={`${item.scenario_id}:${index}`}><td>{NAMES[item.acquisition]}</td><td>{humanizePresentation(line.label)}</td><td>{amount(line.amount, line.unit)}</td><td>{humanizePresentation(line.basis)}</td></tr>))}
    </tbody></table></div>
    <details className="commercial-trace"><summary>Варианты неопределённости</summary>
      <div className="commercial-table-wrap"><table><thead><tr><th>Сценарий</th><th>Профиль</th><th>ROI на CAPEX</th><th>TCO</th><th>NPV</th></tr></thead>
        <tbody>{comparison.scenarios.map((item) => <tr key={item.scenario_id}><td>{NAMES[item.acquisition]}</td><td>{UNCERTAINTY[item.uncertainty]}</td><td>{value(item.metrics.roi)}</td><td>{value(item.metrics.tco)}</td><td>{value(item.metrics.npv)}</td></tr>)}</tbody></table></div>
    </details>
    <div className="commercial-section-title"><div><span>06</span><h2>Чувствительность выбранного сценария</h2></div><p>Все значения ±10% рассчитаны сервером для выбранного профиля.</p></div>
    <label>Сценарий и профиль <select value={active.scenario_id} onChange={(event) => setSelected(event.target.value)}>
      {[comparison.baseline, ...comparison.scenarios].map((item) => <option key={item.scenario_id} value={item.scenario_id}>{NAMES[item.acquisition]} · {UNCERTAINTY[item.uncertainty]}</option>)}
    </select></label>
    <div className="commercial-table-wrap"><table><thead><tr><th>Параметр</th><th>Вариант</th><th>Исходное значение</th><th>±10%</th><th>Изменение NPV</th><th>Источник</th></tr></thead>
      <tbody>{variants.map((item) => <tr key={`${item.parameter}:${item.direction}`}><td>{PARAMETERS[item.parameter] || 'Условие сценария'}</td><td>{item.direction === 'LOWER' ? '−10%' : '+10%'}</td><td>{amount(item.base_value, item.unit)}</td><td>{amount(item.variant_value, item.unit)}</td><td>{item.status === 'COMPLETE' ? amount(item.delta_npv, 'RUB') : 'Недостаточно исходных данных'}</td><td>Сохранённый расчёт</td></tr>)}</tbody></table></div>
    <p>Неподтверждённая цена и характеристики модели остаются предварительными условиями; таблица не является рекомендацией к закупке.</p>
  </section>;
}
