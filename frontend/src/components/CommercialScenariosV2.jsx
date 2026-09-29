import { useMemo, useState } from 'react';

import {
  applyCommercialInputEdit,
  createCommercialSession,
  formatServerMoney,
} from '../commercialScenariosModel';
import FinalEconomicsComparison from './FinalEconomicsComparison';
import ProjectWhatIf from './ProjectWhatIf';
import { roleLabel } from '../roleLabels';
import { fieldPresentation, humanizePresentation, presentationValue, reasonLabel, sourceLabel, statusLabel } from '../presentation';
import { formatDecimal, formatPercent } from '../displayNumber';

const STATUS_LABELS = {
  COMPLETE: 'Рассчитано', INCOMPLETE: 'Недостаточно данных',
  RECOMMENDED: 'Рекомендовано', PRELIMINARY: 'Предварительно',
  ALTERNATIVE: 'Альтернатива', NO_POSITIVE_CASE: 'Нет положительного кейса',
};

export default function CommercialScenariosV2({ bundle, projectName, project, run, onComplete, onRecalculate, onRestart, hasVisualization = false }) {
  const initial = useMemo(() => createCommercialSession(bundle), [bundle]);
  const [session, setSession] = useState(initial);
  const [scenarioKey, setScenarioKey] = useState('PURCHASE:BASE');

  const edit = (field, value) => setSession((current) => applyCommercialInputEdit(current, field, value));
  const scenario = session.result?.scenarios.find((item) => item.key === scenarioKey) || null;
  const finalComparison = bundle.comparison || null;

  return (
    <main className="commercial-screen" id="economics-result" aria-label="Коммерческие сценарии">
      <header className="commercial-header">
        <div>
          <span>ЭКОНОМИКА РОБОТИЗАЦИИ</span>
          <h1>Без роботов, покупка и аренда</h1>
          {projectName && <p>Проект: {projectName}</p>}
          <p>Сохранённые варианты покупки и аренды. Источник — расчёт потребного парка.</p>
          <p>Шесть серверных сценариев. Интерфейс не пересчитывает финансовые показатели.</p>
        </div>
        <div className="commercial-header-actions">
          {hasVisualization && <button type="button" onClick={() => document.getElementById('visualization')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>К 2D и 3D</button>}
          <button type="button" onClick={onRestart}>Новый расчёт</button>
        </div>
      </header>
      <ProjectWhatIf project={project} run={run} onComplete={onComplete} onCreateVersion={onRecalculate} onPhysical={onRecalculate} />

      <section className="commercial-inputs" aria-label="Коммерческие исходные данные">
        <div className="commercial-section-title"><div><span>01</span><h2>Исходные данные</h2></div><p>После изменения полей сохранённый результат нужно пересчитать.</p></div>
        <div className="commercial-input-grid">
            <Input label="Цена одного робота, ₽" value={session.inputs.purchasePrice} readOnly={Boolean(finalComparison)} onChange={(value) => edit('purchasePrice', value)} />
          <ReadOnly label="Налоговая база покупки" value={humanizePresentation(session.inputs.purchaseTaxBasis)} />
          <Input label="Тариф аренды робота, ₽ в месяц" value={session.inputs.raasRate} readOnly={Boolean(finalComparison)} onChange={(value) => edit('raasRate', value)} />
          <ReadOnly label="Налоговая база аренды" value={humanizePresentation(session.inputs.raasTaxBasis)} />
          {bundle.roles.filter((role) => Number(role.headcount) > 0).map((role) => (
            <Input
              key={role.role_id}
              label={`${roleLabel(role.role_code)} · начислено до НДФЛ, ₽/чел./мес.`}
              value={session.inputs.roleSalaries[role.role_id]}
              readOnly={Boolean(finalComparison)}
              placeholder="Нужно для денежного расчёта"
              onChange={(value) => edit(`roleSalaries.${role.role_id}`, value)}
            />
          ))}
        </div>
        {finalComparison && <p>Цена: {formatServerMoney(finalComparison.inputs.price.value)}; база {humanizePresentation(finalComparison.inputs.price.tax_basis)}, НДС {formatPercent(finalComparison.inputs.price.vat_rate)}, источник — сохранённые условия цены. Выработка сотрудника: {presentationValue('', finalComparison.inputs.manual_productivity.value, finalComparison.inputs.manual_productivity.unit)}. Объём: {presentationValue('', finalComparison.inputs.demand.value, finalComparison.inputs.demand.unit)}. <button type="button" className="secondary-action" onClick={onRecalculate}>Изменить подтверждённые входы и создать новую версию</button></p>}
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

          {scenario && <ScenarioDetails scenario={scenario} roles={session.result.roles} />}

          {finalComparison ? <FinalEconomicsComparison comparison={finalComparison} /> : <SensitivityPanel variants={session.result.sensitivity} />}

          <section className="commercial-trace" aria-label="Ограничения расчёта"><h2>Что нужно проверить</h2>
            <p>Технический подбор: {statusLabel(session.result.ranking.technical.status)}; {session.result.ranking.technical.reason_codes?.map(reasonLabel).join('; ') || 'сохранённых замечаний нет'}.</p>
            <p>Финансовое ранжирование: {statusLabel(session.result.ranking.financial.status)}; оно отдельно от денежного вывода выбранной вкладки.</p>
            <ul>{session.result.limitations.map((item) => <li key={item}>{humanizePresentation(item)}</li>)}</ul>
          </section>


        </>
      )}
    </main>
  );
}

function ScenarioDetails({ scenario, roles }) {
  const allocation = scenario.allocation;
  return (
    <section className="commercial-details" aria-label={`Сценарий ${scenario.label}`}>
      <div className="commercial-section-title"><div><span>03</span><h2>{scenario.label}</h2></div><p>Состояние расчёта: {statusLabel(scenario.financial.status)}</p></div>
      <div className="commercial-status-grid">
        <StatusCard title="Условия закупки" status={scenario.procurement.ready ? 'READY' : scenario.procurement.status}>
          <p>Исходная цена: {scenario.procurement.rawAmount == null ? 'не предоставлена' : presentationValue('', scenario.procurement.rawAmount, scenario.procurement.currency)}</p>
          <p>Цена с налогами: {formatServerMoney(scenario.procurement.cashGross)}</p>
          <p>Налоговая база: {humanizePresentation(scenario.procurement.taxBasis)}</p>
          <p>Ставка НДС: {formatPercent(scenario.procurement.vatRate)}</p>
          <p>Риск поставки: {statusLabel(scenario.procurement.supplyRisk)}</p>
          {!scenario.procurement.ready && <p>Предварительное условие; требуется предложение поставщика с ценой, сроком действия и доступностью заказа.</p>}
          {scenario.procurement.blockers.length > 0 && <p>Условия поставки требуют уточнения.</p>}
          {scenario.procurement.blockers.length > 0 && <p>Требуется уточнить условия поставки.</p>}
        </StatusCard>
        <StatusCard title="Денежный результат" status={scenario.financial.status}>
          <strong>{scenario.financial.npvProject}</strong><span>{scenario.financial.npvScope === 'PROJECT_C18' ? 'Эффект проекта с учётом общих затрат · NPV' : 'Эффект операции до общих затрат · NPV; эффект проекта в этой версии не сохранён'}</span>
          {scenario.financial.npvScope === 'PROJECT_C18' && <details><summary>Эффект операции до общих затрат · NPV</summary><strong>{scenario.financial.directProcessNpv}</strong><p>Промежуточная оценка выбранной операции. Общие расходы учитываются в эффекте проекта выше.</p></details>}
          <strong>{scenario.financial.simplePayback}</strong><span>Простой срок окупаемости {scenario.financial.paybackScope === 'PROJECT_C18' ? 'проекта' : 'прямого процесса'}</span>
          <strong>{scenario.financial.discountedPayback}</strong><span>Дисконтированный срок {scenario.financial.paybackScope === 'PROJECT_C18' ? 'проекта' : 'прямого процесса'}</span>
        </StatusCard>
        <StatusCard title="Вывод по сценарию" status={scenario.financial.status}>
          <p>{scenario.financial.projectNpvValue == null ? 'Проектный денежный вывод для этой версии не сохранён.' : Number(scenario.financial.projectNpvValue) > 0 ? 'Сохранённый проектный NPV положителен для выбранных условий.' : Number(scenario.financial.projectNpvValue) < 0 ? 'Сохранённый проектный NPV отрицателен для выбранных условий.' : 'Сохранённый проектный NPV равен нулю.'}</p>
          <p>{scenario.financial.discountedPayback === 'Не достигнута' ? 'Дисконтированная окупаемость за горизонт не достигнута.' : `Дисконтированная окупаемость: ${scenario.financial.discountedPayback}.`}</p>
          {!scenario.procurement.ready && <p>Доступность поставки и условия предложения нужно подтвердить у поставщика; принятие расчётной цены этого не подтверждает.</p>}
          {scenario.recommendation.reason_codes?.includes('financial-ranking-not-confirmed') && <p>Сравнение моделей пока не даёт подтверждённой финансовой рекомендации.</p>}
          {scenario.recommendation.reason_codes?.includes('project-effect-non-positive') && <p>По сохранённому проектному потоку положительный эффект не подтверждён.</p>}
        </StatusCard>
      </div>

      <div className="commercial-ledger-grid">
        <article>
          <h3>Денежные потоки по годам ({scenario.financial.npvScope === 'PROJECT_C18' ? 'проект с общими затратами' : 'прямой процесс'})</h3>
          <div className="commercial-table-wrap"><table><thead><tr><th>Год</th><th>Без роботов</th><th>С роботом</th><th>Разница</th><th>Источник</th></tr></thead><tbody>
            {scenario.financial.annualLedgers.map((row) => <tr key={row.year}><td>{row.year}</td><td>{formatServerMoney(row.baseline)}</td><td>{formatServerMoney(row.scenario)}</td><td>{formatServerMoney(row.delta)}</td><td>Сохранённые годовые потоки</td></tr>)}
          </tbody></table></div>
        </article>
        <article>
          <h3>Расходы</h3>
          <ul className="commercial-expenses">{scenario.expenses.map((line) => <li key={line.line_id}><span><strong>{humanizePresentation(line.label)}</strong><small>Сохранённая статья затрат</small></span><b>{line.amount == null ? statusLabel(line.status) : formatServerMoney(line.amount)}</b></li>)}</ul>
        </article>
      </div>

      <div className="commercial-ledger-grid">
        <article>
          <h3>Персонал до роботизации</h3>
          <div className="commercial-table-wrap"><table><thead><tr><th>Роль</th><th>Сейчас</th><th>Высвобождено</th><th>Остаётся</th></tr></thead><tbody>
            {allocation.role_conservation.map((role) => <tr key={role.role_id}><td>{roleLabel(roles.find((item) => item.role_id === role.role_id)?.role_code)}</td><td>{formatDecimal(role.headcount) ?? '—'}</td><td>{formatDecimal(role.released) ?? '—'}</td><td>{formatDecimal(role.remaining) ?? '—'}</td></tr>)}
          </tbody></table></div>
          <h3>Управление и обслуживание после роботизации</h3>
          <p className="commercial-note">Диспетчеры: требуется {allocation.control_required_once} чел.; техники: {allocation.technicians_required_once} чел. Учтены один раз по общему парку.</p>
          {scenario.staffing && <p>Перевод на пульт: {formatDecimal(scenario.staffing.control_transferred) ?? 'не указано'} чел.; новый найм: {formatDecimal(scenario.staffing.control_additional) ?? 'не указано'} чел.; техники: перевод {formatDecimal(scenario.staffing.technicians_transferred) ?? 'не указано'}, оплачиваемая функция {formatDecimal(scenario.staffing.technicians_billable) ?? 'не указано'}. Основание: сохранённый расчёт труда и политика нагрузки.</p>}
        </article>
        <article>
          <h3>Допущения и источники</h3>
          {scenario.assumptions.map((item) => <details key={item.assumption_id}><summary>{humanizePresentation(item.label)}</summary><p>{presentationValue('', item.value, item.unit)}</p><small>{sourceLabel({ source: item.provenance_ref })}. Полное основание — в архиве.</small></details>)}
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
          {variant.status === 'BLOCKED' && <small>Для оценки не хватает подтверждённых данных.</small>}
        </div>
      ))}</div>
    </section>
  );
}

function StatusCard({ title, status, children }) {
  return <article className="commercial-status-card"><header><h3>{title}</h3><span>{STATUS_LABELS[status] || statusLabel(status)}</span></header>{children}</article>;
}

function Input({ label, value, onChange, placeholder = '', readOnly = false }) {
  return <label><span>{label}</span><input type="number" min="0" step="any" value={value} placeholder={placeholder} readOnly={readOnly} aria-readonly={readOnly} onChange={(event) => onChange(event.target.value)} /></label>;
}

function ReadOnly({ label, value }) {
  return <label><span>{label}</span><input value={value} readOnly aria-readonly="true" /></label>;
}
