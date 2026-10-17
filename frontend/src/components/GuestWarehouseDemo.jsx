import { useState } from 'react';
import packageData from '../warehouseGuestPackageV2.json' with { type: 'json' };
import comparisonData from '../warehouseGuestComparisonV1.json' with { type: 'json' };
import { formatServerMoney } from '../commercialScenariosModel';
import { formatServerQuantity } from '../capacityResultsModel';
import { formatFleet } from '../displayNumber';
import { fieldPresentation, statusLabel } from '../presentation';
import Simulation2DReport from './Simulation2DReport';
import CinematicScene from './CinematicScene';

const acquisitionLabel = { PURCHASE: 'Покупка', RAAS: 'Аренда роботов' };
const uncertaintyLabel = { PESSIMISTIC: 'Пессимистичный', BASE: 'Базовый', OPTIMISTIC: 'Оптимистичный' };
const assetRoot = '/demo/warehouse-pallet-v2';

export default function GuestWarehouseDemo({ onContinue, onBack }) {
  const [selectedScenario, setSelectedScenario] = useState('base');
  const { assumptions, chain, limitations, provenance } = packageData;
  const chosen = selectedScenario === 'base' ? packageData : comparisonData;
  const { demo, simulation, bindings } = chosen;
  const baseFleet = Number(packageData.demo.capacity.value.selected_fleet);
  const peakFleet = Number(comparisonData.demo.capacity.value.selected_fleet);
  const currentPurchase = demo.scenarios.find((item) => item.acquisition === 'PURCHASE' && item.uncertainty === 'BASE');
  const purchaseYear = currentPurchase?.annual_ledgers?.[0];
  const baseline = purchaseYear?.primary_cf_base;
  return <main className="guest-warehouse-demo" aria-label="Паллетная перевозка на типовом складе">
    <header className="guest-demo-card guest-demo-intro">
      <div className="guest-demo-intro-grid">
        <div className="guest-demo-intro-copy"><p className="guest-demo-eyebrow">Готовый пример · два расчёта одного склада · {packageData.as_of}</p>
          <h1>Два сценария работы склада</h1>
          <p>Роботы перевозят подготовленные паллеты к отгрузке. Поменяйте нагрузку и сравните парк, движение и денежный результат.</p>
        </div>
        <div className="guest-demo-choice" role="group" aria-label="Нагрузка склада">
          <button type="button" aria-pressed={selectedScenario === 'base'} onClick={() => setSelectedScenario('base')}><span>01 · Обычная нагрузка</span><strong>2 000 паллет/сутки</strong><small>{baseFleet} роботов</small></button>
          <button type="button" aria-pressed={selectedScenario === 'peak'} onClick={() => setSelectedScenario('peak')}><span>02 · Нагрузка +20 %</span><strong>2 400 паллет/сутки</strong><small>{formatFleet(peakFleet)}</small></button>
        </div>
      </div>
      <div className="guest-demo-impact" role="status"><strong>Что меняется:</strong> спрос +20 % → расчётный парк +{peakFleet - baseFleet} робота. Максимальная очередь в сохранённой модели: {selectedScenario === 'base' ? packageData.simulation.report.queue.maximum_jobs : comparisonData.simulation.report.queue.maximum_jobs} задание. Сценарный NPV покупки: {formatServerMoney(currentPurchase?.npv_project?.value)}. Парк и экономика пересчитаны для выбранного варианта.</div>
      <p className="guest-demo-choice-note">Заранее вычисленные примеры · ваши данные сюда не вводятся и на сервер не отправляются.</p>
    </header>

    <section className="guest-demo-card guest-demo-robot" aria-label="Выбранный робот">
      <div><span className="guest-demo-step">01 · ВЫБРАННЫЙ РОБОТ</span><h2>Авторский профиль MULE</h2><p>Один профиль для обоих сценариев: перевозка подготовленной паллеты, плечо 120 м, обмен 90 с. Это входы примера. Грузоподъёмность, проезд с грузом и поставка требуют проверки.</p></div>
      <span className="guest-demo-robot-badge">Модель для демонстрации · не подтверждённая рекомендация</span>
    </section>

    <section className="guest-demo-simulation" aria-label="Сохранённая симуляция">
      <div className="guest-demo-stage-heading"><div><span className="guest-demo-step">02 · РАБОТА СКЛАДА</span><h2>{selectedScenario === 'base' ? 'Обычная нагрузка' : 'Нагрузка +20 %'}</h2></div><p>Переключите 2D и 3D прямо в сцене. Показывается сохранённый физический расчёт выбранного варианта.</p></div>
      <CinematicScene selectedScenario={selectedScenario} onSelectScenario={setSelectedScenario}
        fleet={demo.capacity.value.selected_fleet} queue={simulation.report.queue.maximum_jobs}
        npv={formatServerMoney(currentPurchase?.npv_project?.value)} resultDigest={demo.result_digest}>
        <Simulation2DReport key={simulation.request.request_id} request={simulation.request} initialReport={simulation.report} autoPlay initialViewMode="3D" compact />
      </CinematicScene>
      <p className="guest-demo-simulation-note">2D и 3D показывают один сохранённый сценарий. Координаты условные; показатели взяты из отчёта симуляции. Рост спроса заново пересчитал парк и экономику.</p>
    </section>

    <details className="guest-demo-card guest-demo-intro-details"><summary>Что одинаково в двух сценариях и откуда взяты данные</summary>
      <p>{comparisonData.difference}</p><p className="guest-demo-caution">{demo.model_notice}. Результат предварительный: проверка на объекте и коммерческие условия не подтверждены. План конкретного склада не загружен.</p>
    </details>

    <section className="guest-demo-card guest-demo-conclusion" aria-label="Вывод двух сценариев">
      <span className="guest-demo-step">03 · ЧТО МЕНЯЕТСЯ</span>
      <h2>При росте потока на 400 паллет в сутки расчётный парк меняется с {baseFleet} до {peakFleet} роботов</h2>
      <p>В обоих вариантах сохраняются маршрут 120 м, две смены по 11 часов, обмен 90 секунд и денежные допущения. Сервер отдельно пересчитал мощность, симуляцию и экономику. План реального объекта и фактическая пригодность ещё не подтверждены.</p>
      <div className="guest-demo-before-after"><article><span>Текущая паллетная операция · без роботов</span><strong>{formatServerMoney(Math.abs(Number(baseline)))}</strong><small>Сценарный отток денег за 1-й год</small></article><article><span>С покупкой расчётного парка</span><strong>{formatServerMoney(Math.abs(Number(purchaseYear?.primary_cf_scenario)))}</strong><small>Сценарный отток денег за 1-й год, включая вложения модели</small></article><div>Разница денежных потоков 1-го года: <strong>{formatServerMoney(purchaseYear?.differential_cf)}</strong></div></div>
      <div className="guest-demo-comparison"><div><span>Выбранный вариант</span><strong>{selectedScenario === 'base' ? '2 000' : '2 400'} паллет/сутки</strong></div><div><span>Парк</span><strong>{formatFleet(demo.capacity.value.selected_fleet)}</strong></div><div><span>Максимальная очередь модели</span><strong>{simulation.report.queue.maximum_jobs} задание</strong></div><div><span>NPV · покупка, базовый профиль</span><strong>{formatServerMoney(currentPurchase?.npv_project?.value)}</strong></div></div>
      <p className="guest-demo-caution">NPV относится только к перевозке подготовленных паллет и использует сценарные цены и зарплаты. Это не финансовый итог всего склада.</p>
    </section>

    <section className="guest-demo-card" aria-label="Отчёты и данные примера"><h2>Проверить расчёт</h2>
      <div className="guest-demo-actions">
        <a className="primary-action" href={selectedScenario === 'base' ? '/demo/warehouse-pallet-investor-v1/report.pdf' : '/demo/warehouse-comparison-v1/report.pdf'} download={selectedScenario === 'base' ? 'warehouse-pallet-base-v1.pdf' : 'warehouse-pallet-peak-v1.pdf'}>Отчёт PDF · выбранный вариант</a>
        <a className="secondary-action" href={`${assetRoot}/evidence.zip`} download="warehouse-pallet-demo-v2.zip">Архив расчёта · обычная нагрузка</a>
        <a className="secondary-action" href="/demo/warehouse-comparison-v1/scenario.json" download="warehouse-pallet-peak-v1.json">Данные и контрольные суммы · нагрузка +20 %</a>
      </div>
    </section>

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
        <tr><td>Фасовка</td><td>Фасовщик</td><td>Не рассчитано</td></tr>
      </tbody></table></div>
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
      <p>Пакет: {chosen.schema_version}. Условия: {assumptions.schema_version}. Сценарий: {bindings.scenario_revision_id}.</p>
      <p>Вход: {bindings.capacity_economics_input_digest}. Экономика: {bindings.economics_result_digest}. Симуляция: {bindings.simulation_report_digest}.</p>
      <a href={selectedScenario === 'base' ? `${assetRoot}/manifest.json` : '/demo/warehouse-comparison-v1/scenario.json'} download>Скачать данные выбранного варианта</a>
    </details>
  </main>;
}
