import { useMemo, useState } from 'react';

import {
  applyCommercialInputEdit,
  createCommercialSession,
  formatServerMoney,
} from '../commercialScenariosModel';
import { buildEconomicsSimulationRequest } from '../economicsSimulationRequest';
import Simulation2DReport from './Simulation2DReport';

const STATUS_LABELS = {
  COMPLETE: 'Рассчитано', INCOMPLETE: 'Недостаточно данных',
  RECOMMENDED: 'Рекомендовано', PRELIMINARY: 'Предварительно',
  ALTERNATIVE: 'Альтернатива', NO_POSITIVE_CASE: 'Нет положительного кейса',
};

export default function CommercialScenariosV2({ bundle, scenarioSpec, onRecalculate, onRestart }) {
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
          <span>COMMERCIAL SCENARIOS V2 · REVISION {bundle.input_revision}</span>
          <h1>Покупка и RaaS</h1>
          <p>Шесть серверных сценариев. Интерфейс не пересчитывает финансовые показатели.</p>
        </div>
        <div className="commercial-header-actions">
          {simulationRequest && <a href="#visualization">К 2D и 3D</a>}
          <button type="button" onClick={onRestart}>Новый расчёт</button>
        </div>
      </header>

      <section className="commercial-inputs" aria-label="Коммерческие исходные данные">
        <div className="commercial-section-title"><div><span>01</span><h2>Исходные данные</h2></div><p>Любое изменение инвалидирует показанный AnalysisRun.</p></div>
        <div className="commercial-input-grid">
          <Input label="Цена оборудования, RUB/robot" value={session.inputs.purchasePrice} onChange={(value) => edit('purchasePrice', value)} />
          <ReadOnly label="Налоговая база покупки" value={session.inputs.purchaseTaxBasis} />
          <Input label="Ставка RaaS, raw" value={session.inputs.raasRate} onChange={(value) => edit('raasRate', value)} />
          <ReadOnly label="Налоговая база RaaS" value={session.inputs.raasTaxBasis} />
          {bundle.roles.map((role) => (
            <Input
              key={role.role_id}
              label={`${role.role_code} · gross RUB/person/month`}
              value={session.inputs.roleSalaries[role.role_id]}
              placeholder="Обязательно для finance"
              onChange={(value) => edit(`roleSalaries.${role.role_id}`, value)}
            />
          ))}
        </div>
        {bundle.roles.some((role) => role.monthly_gross_salary.status === 'MISSING') && (
          <p className="commercial-warning" role="status">Есть роль без monthly gross salary: technical result доступен, finance остаётся INCOMPLETE.</p>
        )}
        {session.stale && (
          <div className="commercial-stale" role="alert">
            <div><strong>Результат устарел</strong><p>Поля изменены: {session.dirtyFields.join(', ')}. Старые NPV/payback скрыты.</p></div>
            <button type="button" onClick={() => onRecalculate?.(session.inputs)}>Пересчитать на сервере</button>
          </div>
        )}
      </section>

      {!session.stale && session.result && (
        <>
          <section className="commercial-scenario-section" aria-label="Шесть коммерческих сценариев">
            <div className="commercial-section-title"><div><span>02</span><h2>Сценарии</h2></div><p>Purchase/RaaS × uncertainty. Статусы независимы.</p></div>
            <div className="commercial-tabs">
              {session.result.scenarios.map((item) => (
                <button key={item.key} type="button" className={item.key === scenarioKey ? 'active' : ''} onClick={() => setScenarioKey(item.key)}>
                  <strong>{item.label}</strong>
                  <small>{STATUS_LABELS[item.recommendation.status] || item.recommendation.status}</small>
                </button>
              ))}
            </div>
          </section>

          {scenario && <ScenarioDetails scenario={scenario} />}

          <SensitivityPanel variants={session.result.sensitivity} />

          <section className="commercial-trace" aria-label="Версии и ограничения">
            <div className="commercial-section-title"><div><span>05</span><h2>Trace и версии</h2></div><p>Все значения привязаны к server contracts.</p></div>
            <dl>{Object.entries(session.result.versions).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
            <ul>{session.result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </section>

          {simulationRequest && <div className="commercial-visualization">
            <p>2D и 3D используют ScenarioSpec этого immutable run. Для C23 не заданы SLA и мощности погрузочных ресурсов; геометрия синтетическая и не является проектом площадки. Отчёт C23 сохраняется отдельным неизменяемым evidence, связанным с этим run.</p>
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
      <div className="commercial-section-title"><div><span>03</span><h2>{scenario.label}</h2></div><p>Run status: {scenario.financial.status}</p></div>
      <div className="commercial-status-grid">
        <StatusCard title="Procurement" status={scenario.procurement.ready ? 'READY' : scenario.procurement.status}>
          <p>Raw: {scenario.procurement.rawAmount == null ? 'не предоставлено' : `${scenario.procurement.rawAmount} ${scenario.procurement.currency}`}</p>
          <p>Cash gross: {formatServerMoney(scenario.procurement.cashGross)}</p>
          <p>Tax basis: {scenario.procurement.taxBasis}</p>
          <p>VAT rate: {scenario.procurement.vatRate == null ? 'не задана; frontend не угадывает' : scenario.procurement.vatRate}</p>
          <p>Supply risk: {scenario.procurement.supplyRisk}</p>
          {scenario.procurement.blockers.map((item) => <code key={item}>{item}</code>)}
        </StatusCard>
        <StatusCard title="Financial" status={scenario.financial.status}>
          <strong>{scenario.financial.npvProject}</strong><span>NPV project</span>
          <strong>{scenario.financial.simplePayback}</strong><span>Simple payback</span>
          <strong>{scenario.financial.discountedPayback}</strong><span>Discounted payback</span>
        </StatusCard>
        <StatusCard title="Recommendation" status={scenario.recommendation.status}>
          <p>{scenario.recommendation.candidate_id || 'Кандидат не выбран'}</p>
          {(scenario.recommendation.reason_codes || []).map((item) => <code key={item}>{item}</code>)}
        </StatusCard>
      </div>

      <div className="commercial-ledger-grid">
        <article>
          <h3>Baseline / scenario / delta</h3>
          <div className="commercial-table-wrap"><table><thead><tr><th>Год</th><th>Baseline CF</th><th>Scenario CF</th><th>Delta</th><th>Sources</th></tr></thead><tbody>
            {scenario.financial.annualLedgers.map((row) => <tr key={row.year}><td>{row.year}</td><td>{formatServerMoney(row.baseline)}</td><td>{formatServerMoney(row.scenario)}</td><td>{formatServerMoney(row.delta)}</td><td>{row.sourceRefs.join(', ') || 'financial trace'}</td></tr>)}
          </tbody></table></div>
        </article>
        <article>
          <h3>Расходы</h3>
          <ul className="commercial-expenses">{scenario.expenses.map((line) => <li key={line.line_id}><span><strong>{line.label}</strong><small>{line.source_ref}</small></span><b>{line.amount == null ? line.status : formatServerMoney(line.amount)}</b></li>)}</ul>
        </article>
      </div>

      <div className="commercial-ledger-grid">
        <article>
          <h3>Роли и object-level staff</h3>
          <div className="commercial-table-wrap"><table><thead><tr><th>Роль</th><th>Headcount</th><th>Released</th><th>Remaining</th></tr></thead><tbody>
            {allocation.role_conservation.map((role) => <tr key={role.role_id}><td>{role.role_id}</td><td>{role.headcount}</td><td>{role.released}</td><td>{role.remaining}</td></tr>)}
          </tbody></table></div>
          <p className="commercial-note">Пульт: {allocation.control_required_once} · Technical staff: {allocation.technicians_required_once}. Учтены backend один раз.</p>
        </article>
        <article>
          <h3>Допущения и источники</h3>
          {scenario.assumptions.map((item) => <details key={item.assumption_id}><summary>{item.label}</summary><p>{item.value} {item.unit}</p><code>{item.provenance_ref}</code></details>)}
          <p className="commercial-note">Sources: {scenario.sourceRefs.join(', ')}</p>
        </article>
      </div>
    </section>
  );
}

function SensitivityPanel({ variants }) {
  return (
    <section className="commercial-sensitivity" aria-label="Sensitivity ±10%">
      <div className="commercial-section-title"><div><span>04</span><h2>Sensitivity ±10%</h2></div><p>Готовые server deltas; длина полос не вычисляется в браузере.</p></div>
      <div className="commercial-tornado">{variants.map((variant) => (
        <div key={variant.id} className={`direction-${variant.direction.toLowerCase()}`}>
          <span>{variant.parameter} · {variant.direction}</span>
          <strong>{variant.status === 'BLOCKED' ? 'BLOCKED' : formatServerMoney(variant.deltaNpv, variant.unit)}</strong>
          <small>{variant.reasons.join(', ')}</small>
        </div>
      ))}</div>
    </section>
  );
}

function StatusCard({ title, status, children }) {
  return <article className="commercial-status-card"><header><h3>{title}</h3><span>{STATUS_LABELS[status] || status}</span></header>{children}</article>;
}

function Input({ label, value, onChange, placeholder = '' }) {
  return <label><span>{label}</span><input type="number" min="0" step="any" value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /></label>;
}

function ReadOnly({ label, value }) {
  return <label><span>{label}</span><input value={value} readOnly aria-readonly="true" /></label>;
}
