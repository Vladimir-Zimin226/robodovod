import { useMemo, useState } from 'react';

import {
  applyCommercialInputEdit,
  createCommercialSession,
  formatServerMoney,
} from '../commercialScenariosModel';
import { buildEconomicsSimulationRequest } from '../economicsSimulationRequest';
import Simulation2DReport from './Simulation2DReport';
import { fieldPresentation, humanizePresentation, statusLabel } from '../presentation';

const STATUS_LABELS = {
  COMPLETE: 'Рассчитано', INCOMPLETE: 'Недостаточно данных',
  RECOMMENDED: 'Рекомендовано', PRELIMINARY: 'Предварительно',
  ALTERNATIVE: 'Альтернатива', NO_POSITIVE_CASE: 'Нет положительного кейса',
};

export default function CommercialScenariosV2({ bundle, scenarioSpec, capacityRunId, onRecalculate, onRestart }) {
  const initial = useMemo(() => createCommercialSession(bundle), [bundle]);
  const [session, setSession] = useState(initial);
  const [scenarioKey, setScenarioKey] = useState('PURCHASE:BASE');
  const simulationRequest = useMemo(
    () => buildEconomicsSimulationRequest(bundle, scenarioSpec), [bundle, scenarioSpec],
  );

  const edit = (field, value) => setSession((current) => applyCommercialInputEdit(current, field, value));
  const scenario = session.result?.scenarios.find((item) => item.key === scenarioKey) || null;

  return (
    <main className="commercial-screen" aria-label="Коммерческие сценарии">
      <header className="commercial-header">
        <div>
          <span>ЭКОНОМИКА РОБОТИЗАЦИИ</span>
          <h1>Покупка и аренда</h1>
          <p>Сохранённые варианты покупки и аренды. Источник — расчёт потребного парка.</p>
          <details><summary>Технические подробности</summary><p>Расчёт экономики: {bundle.run_id}. Исходный расчёт парка: {capacityRunId || 'не указан'}. Версия ввода: {bundle.input_revision}.</p></details>
          <p>Шесть серверных сценариев. Интерфейс не пересчитывает финансовые показатели.</p>
        </div>
        <div className="commercial-header-actions">
          {simulationRequest && <a href="#visualization">К 2D и 3D</a>}
          <button type="button" onClick={onRestart}>Новый расчёт</button>
        </div>
      </header>

      <section className="commercial-inputs" aria-label="Коммерческие исходные данные">
        <div className="commercial-section-title"><div><span>01</span><h2>Исходные данные</h2></div><p>После изменения полей сохранённый результат нужно пересчитать.</p></div>
        <div className="commercial-input-grid">
          <Input label="Цена одного робота, ₽" value={session.inputs.purchasePrice} onChange={(value) => edit('purchasePrice', value)} />
          <ReadOnly label="Налоговая база покупки" value={humanizePresentation(session.inputs.purchaseTaxBasis)} />
          <Input label="Тариф аренды робота, ₽ в месяц" value={session.inputs.raasRate} onChange={(value) => edit('raasRate', value)} />
          <ReadOnly label="Налоговая база аренды" value={humanizePresentation(session.inputs.raasTaxBasis)} />
          {bundle.roles.map((role) => (
            <Input
              key={role.role_id}
              label={`${role.role_code === 'forklift_driver' ? 'Водитель погрузчика' : 'Роль процесса'} · зарплата до удержаний, ₽/чел./мес.`}
              value={session.inputs.roleSalaries[role.role_id]}
              placeholder="Нужно для денежного расчёта"
              onChange={(value) => edit(`roleSalaries.${role.role_id}`, value)}
            />
          ))}
        </div>
        {bundle.roles.some((role) => role.monthly_gross_salary.status === 'MISSING') && (
          <p className="commercial-warning" role="status">У одной из ролей нет месячной зарплаты до удержаний: расчёт парка доступен, экономика остаётся частичной.</p>
        )}
        {session.stale && (
          <div className="commercial-stale" role="alert">
            <div><strong>Результат устарел</strong><p>Поля изменены: {session.dirtyFields.map((field) => fieldPresentation(field).label).join(', ')}. Денежные показатели скрыты до нового расчёта.</p></div>
            <button type="button" onClick={() => onRecalculate?.(session.inputs)}>Пересчитать на сервере</button>
          </div>
        )}
      </section>

      {!session.stale && session.result && (
        <>
          <section className="commercial-scenario-section" aria-label="Шесть коммерческих сценариев">
            <div className="commercial-section-title"><div><span>02</span><h2>Сценарии</h2></div><p>Покупка и аренда при трёх вариантах условий.</p></div>
            <div className="commercial-tabs">
              {session.result.scenarios.map((item) => (
                <button key={item.key} type="button" className={item.key === scenarioKey ? 'active' : ''} onClick={() => setScenarioKey(item.key)}>
                  <strong>{item.label}</strong>
                  <small>{STATUS_LABELS[item.recommendation.status] || statusLabel(item.recommendation.status)}</small>
                </button>
              ))}
            </div>
          </section>

          {scenario && <ScenarioDetails scenario={scenario} />}

          <SensitivityPanel variants={session.result.sensitivity} />

          <details className="commercial-trace" aria-label="Версии и ограничения"><summary>Технические подробности</summary>
            <p>Версии и источники сохранённого расчёта.</p>
            <dl>{Object.entries(session.result.versions).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
            <ul>{session.result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </details>

          {simulationRequest && <div className="commercial-visualization">
            <p>Покупка и аренда опираются на общий физический профиль PURCHASE/BASE: тот же парк и график. Финансовые варианты неопределённости и ramp не являются отдельными симуляциями. Выбор физической версии ниже меняет только 2D/3D и её отчёт; денежная таблица выше остаётся результатом расчёта {bundle.run_id}.</p>
            <p>2D и 3D используют сохранённый технический сценарий. Для симуляции не заданы норматив времени и мощности погрузочных ресурсов; геометрия условная и не является проектом площадки. Отчёт симуляции сохраняется отдельно и связан с этим расчётом.</p>
            <Simulation2DReport key={simulationRequest.request_id} request={simulationRequest} analysisRunId={bundle.run_id} />
          </div>}
        </>
      )}
    </main>
  );
}

function ScenarioDetails({ scenario }) {
  const allocation = scenario.allocation;
  return (
    <section className="commercial-details" aria-label={`Сценарий ${scenario.label}`}>
      <div className="commercial-section-title"><div><span>03</span><h2>{scenario.label}</h2></div><p>Состояние расчёта: {statusLabel(scenario.financial.status)}</p></div>
      <div className="commercial-status-grid">
        <StatusCard title="Условия закупки" status={scenario.procurement.ready ? 'READY' : scenario.procurement.status}>
          <p>Исходная цена: {scenario.procurement.rawAmount == null ? 'не предоставлена' : `${scenario.procurement.rawAmount} ${scenario.procurement.currency}`}</p>
          <p>Цена с налогами: {formatServerMoney(scenario.procurement.cashGross)}</p>
          <p>Налоговая база: {humanizePresentation(scenario.procurement.taxBasis)}</p>
          <p>Ставка НДС: {scenario.procurement.vatRate == null ? 'не задана' : scenario.procurement.vatRate}</p>
          <p>Риск поставки: {statusLabel(scenario.procurement.supplyRisk)}</p>
          {scenario.procurement.blockers.length > 0 && <p>Условия поставки требуют уточнения.</p>}
          <details><summary>Технические подробности</summary>{scenario.procurement.blockers.map((item) => <code key={item}>{item}</code>)}</details>
        </StatusCard>
        <StatusCard title="Денежный результат" status={scenario.financial.status}>
          <strong>{scenario.financial.npvProject}</strong><span>Чистая приведённая стоимость проекта</span>
          <strong>{scenario.financial.simplePayback}</strong><span>Простой срок окупаемости</span>
          <strong>{scenario.financial.discountedPayback}</strong><span>Срок окупаемости с дисконтированием</span>
        </StatusCard>
        <StatusCard title="Вывод по сценарию" status={scenario.recommendation.status}>
          <p>{scenario.recommendation.candidate_id ? 'Расчётный вариант выбран' : 'Вариант не выбран'}</p>
          <details><summary>Технические подробности</summary><p>{scenario.recommendation.candidate_id}</p>{(scenario.recommendation.reason_codes || []).map((item) => <code key={item}>{item}</code>)}</details>
        </StatusCard>
      </div>

      <div className="commercial-ledger-grid">
        <article>
          <h3>Денежные потоки по годам</h3>
          <div className="commercial-table-wrap"><table><thead><tr><th>Год</th><th>Без роботов</th><th>С роботом</th><th>Разница</th><th>Источник</th></tr></thead><tbody>
            {scenario.financial.annualLedgers.map((row) => <tr key={row.year}><td>{row.year}</td><td>{formatServerMoney(row.baseline)}</td><td>{formatServerMoney(row.scenario)}</td><td>{formatServerMoney(row.delta)}</td><td><details><summary>Проверить</summary>{row.sourceRefs.join(', ') || 'ход денежного расчёта'}</details></td></tr>)}
          </tbody></table></div>
        </article>
        <article>
          <h3>Расходы</h3>
          <ul className="commercial-expenses">{scenario.expenses.map((line) => <li key={line.line_id}><span><strong>{line.label}</strong><details><summary>Источник</summary><small>{line.source_ref}</small></details></span><b>{line.amount == null ? statusLabel(line.status) : formatServerMoney(line.amount)}</b></li>)}</ul>
        </article>
      </div>

      <div className="commercial-ledger-grid">
        <article>
          <h3>Роли и численность на объекте</h3>
          <div className="commercial-table-wrap"><table><thead><tr><th>Роль</th><th>Сейчас</th><th>Высвобождено</th><th>Остаётся</th></tr></thead><tbody>
            {allocation.role_conservation.map((role, index) => <tr key={role.role_id}><td>Роль {index + 1}<details><summary>Идентификатор</summary>{role.role_id}</details></td><td>{role.headcount}</td><td>{role.released}</td><td>{role.remaining}</td></tr>)}
          </tbody></table></div>
          <p className="commercial-note">Диспетчеры: {allocation.control_required_once} · технические специалисты: {allocation.technicians_required_once}. Учтены в расчёте один раз.</p>
        </article>
        <article>
          <h3>Допущения и источники</h3>
          {scenario.assumptions.map((item) => <details key={item.assumption_id}><summary>{humanizePresentation(item.label)}</summary><p>{item.value} {item.unit}</p><code>{item.provenance_ref}</code></details>)}
          <details className="commercial-note"><summary>Технические источники</summary>{scenario.sourceRefs.join(', ')}</details>
        </article>
      </div>
    </section>
  );
}

function SensitivityPanel({ variants }) {
  return (
    <section className="commercial-sensitivity" aria-label="Чувствительность ±10 %">
      <div className="commercial-section-title"><div><span>04</span><h2>Чувствительность ±10 %</h2></div><p>Готовые значения изменения результата; длина полос не вычисляется в браузере.</p></div>
      <div className="commercial-tornado">{variants.map((variant) => (
        <div key={variant.id} className={`direction-${variant.direction.toLowerCase()}`}>
          <span>{fieldPresentation(variant.parameter).label} · {variant.direction === 'UP' ? 'увеличение' : 'уменьшение'}</span>
          <strong>{variant.status === 'BLOCKED' ? 'не рассчитано' : formatServerMoney(variant.deltaNpv, variant.unit)}</strong>
          <details><summary>Технические причины</summary>{variant.reasons.join(', ')}</details>
        </div>
      ))}</div>
    </section>
  );
}

function StatusCard({ title, status, children }) {
  return <article className="commercial-status-card"><header><h3>{title}</h3><span>{STATUS_LABELS[status] || statusLabel(status)}</span></header>{children}</article>;
}

function Input({ label, value, onChange, placeholder = '' }) {
  return <label><span>{label}</span><input type="number" min="0" step="any" value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /></label>;
}

function ReadOnly({ label, value }) {
  return <label><span>{label}</span><input value={value} readOnly aria-readonly="true" /></label>;
}
