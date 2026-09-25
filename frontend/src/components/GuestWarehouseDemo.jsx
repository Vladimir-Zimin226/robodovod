import packageData from '../warehouseGuestPackage.json' with { type: 'json' };
import { formatServerMoney } from '../commercialScenariosModel';
import { formatServerQuantity } from '../capacityResultsModel';
import { formatFleet } from '../displayNumber';
import { fieldPresentation, statusLabel } from '../presentation';
import Simulation2DReport from './Simulation2DReport';

const acquisitionLabel = { PURCHASE: 'Покупка', RAAS: 'Аренда роботов' };
const uncertaintyLabel = { PESSIMISTIC: 'Пессимистичный', BASE: 'Базовый', OPTIMISTIC: 'Оптимистичный' };
const assetRoot = '/demo/warehouse-pallet-v1';

export default function GuestWarehouseDemo({ onContinue, onBack }) {
  const { demo, assumptions, simulation, chain, limitations, bindings, provenance } = packageData;
  const baseline = demo.scenarios.find((item) => item.uncertainty === 'BASE')?.annual_ledgers?.[0]?.primary_cf_base;
  return <main className="guest-warehouse-demo" aria-label="Паллетная перевозка на типовом складе">
    <header className="guest-demo-card guest-demo-intro">
      <p className="guest-demo-eyebrow">Публичный пример · {packageData.as_of}</p>
      <h1>{packageData.title}</h1>
      <p>{demo.process}</p>
      <p className="guest-demo-caution">{demo.model_notice}. Результат предварительный: проверка на объекте и коммерческие условия не подтверждены.</p>
      <p>Это заранее вычисленный пример; ваши данные сюда не вводятся и на сервер не отправляются.</p>
      <div className="guest-demo-actions">
        <a className="primary-action" href={`${assetRoot}/report.pdf`} download="warehouse-pallet-demo-v1.pdf">Скачать отчёт PDF</a>
        <a className="secondary-action" href={`${assetRoot}/evidence.zip`} download="warehouse-pallet-demo-v1.zip">Скачать полный ZIP</a>
      </div>
    </header>

    <section className="guest-demo-grid" aria-label="Расчёт потребного парка">
      <article className="guest-demo-card"><h2>Потребный парк</h2><strong>{formatFleet(demo.capacity.value.selected_fleet)}</strong><small>Расчёт C11 · {statusLabel(demo.capacity.status)}</small></article>
      <article className="guest-demo-card"><h2>Эффективная мощность</h2><strong>{formatServerQuantity(demo.capacity.value.effective_capacity)}</strong><small>С учётом потерь времени из расчётного профиля</small></article>
      <article className="guest-demo-card"><h2>Покрытие нагрузки</h2><strong>{formatServerQuantity(demo.capacity.value.coverage)}</strong><small>По выбранному сценарию, без обследования объекта</small></article>
    </section>

    <section className="guest-demo-card" aria-label="Экономика демо">
      <h2>Экономика перевозки</h2>
      <p>Денежный поток без роботов за первый год: {formatServerMoney(baseline)}. Ниже сохранённая чистая приведённая стоимость проекта для шести сценариев.</p>
      <div className="guest-demo-scenarios">{demo.scenarios.map((item) => <article key={`${item.acquisition}:${item.uncertainty}`}>
        <h3>{acquisitionLabel[item.acquisition]} · {uncertaintyLabel[item.uncertainty]}</h3>
        <strong>{item.npv_project.status === 'COMPLETE' ? formatServerMoney(item.npv_project.value) : 'не рассчитано'}</strong>
      </article>)}</div>
      <p className="guest-demo-caution">Проверка пригодности на объекте: {statusLabel(demo.c05)} · Закупка: {statusLabel(demo.procurement)}. Положительная экономика не подтверждает пригодность, цену или доступность модели.</p>
    </section>

    <section className="guest-demo-card" aria-label="Охват складских операций">
      <h2>Что входит в пример склада</h2>
      <p>Учтена перевозка подготовленных паллет и труд водителя погрузчика. Объёмы и зарплаты остальных ролей не выводятся из паллетного потока.</p>
      <div className="guest-demo-table-scroll"><table><thead><tr><th>Операция</th><th>Роль</th><th>Статус</th></tr></thead><tbody>
        {chain.map((item) => <tr key={item.operation}><td>{item.operation}</td><td>{item.role}</td><td>{item.status === 'MODELED' ? 'Учтено' : 'Не рассчитано'}</td></tr>)}
      </tbody></table></div>
    </section>

    <section className="guest-demo-simulation" aria-label="Сохранённая симуляция">
      <Simulation2DReport request={simulation.request} initialReport={simulation.report} />
      <p className="guest-demo-simulation-note">2D и 3D показывают один сохранённый сценарий. Схема условная; показатели взяты из отчёта симуляции.</p>
    </section>

    <section className="guest-demo-card" aria-label="Чувствительность демо">
      <h2>Чувствительность</h2>
      <p>Изменение NPV при тестовых отклонениях цены, объёма и зарплаты ±10 %; значения взяты из сохранённого расчётного примера.</p>
      <ul className="guest-demo-detail-grid">{demo.sensitivity.map((item) => <li key={item.variant_id}>
        {fieldPresentation(item.override.parameter_id).label} · {item.override.direction === 'UPPER' ? 'увеличение' : 'уменьшение'}: {item.status === 'BLOCKED' ? 'не рассчитано' : formatServerMoney(item.npv_project.delta_value)}
      </li>)}</ul>
    </section>

    <details className="guest-demo-card"><summary>Исходные допущения и источники</summary>
      <p>{assumptions.source}. Дата {assumptions.published_on}. Числа не являются условиями вашего объекта или поставщика.</p>
      <ul className="guest-demo-detail-grid">{Object.entries(assumptions.fields).map(([field, item]) => <li key={field}><strong>{fieldPresentation(field).label}</strong>: {item.value} {item.unit}. {item.rationale}.</li>)}</ul>
      <p>Прочие входы: дата оценки {assumptions.other_inputs.evaluation_date}; часовой пояс {assumptions.other_inputs.timezone}; владелец инфраструктуры RaaS {assumptions.other_inputs.raas_infrastructure_owner}.</p>
      <h3>Происхождение результатов</h3>
      <ul>{Object.entries(provenance).map(([key, value]) => <li key={key}><strong>{key}</strong>: {value}</li>)}</ul>
    </details>

    <details className="guest-demo-card"><summary>Ограничения примера</summary><ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul></details>
    <div className="guest-demo-actions">
      <button type="button" className="primary-action" onClick={onContinue}>Открыть ввод своего процесса и проект</button>
      <button type="button" className="secondary-action" onClick={onBack}>На главную</button>
    </div>
    <details className="guest-demo-technical"><summary>Версии и контрольные суммы</summary>
      <p>Пакет: {packageData.schema_version}. Условия: {bindings.assumptions_version}. Сценарий: {bindings.scenario_revision_id}.</p>
      <p>Вход: {bindings.capacity_economics_input_digest}. Экономика: {bindings.economics_result_digest}. Симуляция: {bindings.simulation_report_digest}.</p>
      <a href={`${assetRoot}/manifest.json`} download>Скачать manifest</a>
    </details>
  </main>;
}
