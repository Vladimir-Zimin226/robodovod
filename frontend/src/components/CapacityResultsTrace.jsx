import { useMemo } from 'react';
import { formatServerQuantity, getCapacityResultsModel } from '../dashboardModel';
import { formatFleet } from '../displayNumber';
import { zoneForProcessId } from '../processRoleIntakeV2';
import { humanizePresentation, savedCalculationLabel } from '../presentation';

const issueText = (issue) => humanizePresentation(issue.message || issue.code);

export default function CapacityResultsTrace({ response, expectedRevision = null, onRestart, zoneContext = null }) {
  const model = useMemo(
    () => getCapacityResultsModel(response, expectedRevision),
    [response, expectedRevision],
  );

  return (
    <main className="capacity-results-v2 max-w-6xl mx-auto p-6 space-y-5" aria-label="Результат расчёта производительности">
      <header className="bg-white border rounded-2xl p-5">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <p className="text-xs text-slate-500">{savedCalculationLabel(response?.finished_at || response?.created_at)}</p>
            <h1 className="text-2xl font-semibold">Производительность и требуемый парк</h1>
            <p className="text-sm text-slate-600 mt-1">Процесс: {model.processId}</p>
            {model.processId?.includes('warehouse_receiving_shipping') && <p className="mt-1 text-sm text-amber-800">Учтена перевозка подготовленных паллет; отбор коробок и упаковка не рассчитаны. Экономия относится только к роли, связанной с перевозкой.</p>}
            <p className="text-xs text-slate-500">Зона: {zoneContext?.label || zoneForProcessId(model.processId)} · расчёт охватывает только указанный процесс и не суммирует общие ресурсы других зон.</p>
            {zoneContext?.constraints_note && <p className="text-xs text-amber-700">Ограничения зоны: {zoneContext.constraints_note} · не включены в проверку пригодности на объекте.</p>}
          </div>
          <div className="text-right">
            <span className="inline-flex rounded-full bg-blue-50 text-blue-700 px-3 py-1 text-sm font-semibold">{model.statusLabel}</span>
            <details className="text-xs text-slate-500 mt-2"><summary>Технические подробности</summary><p>Расчёт: {model.runId}. Версия ввода: {model.revision}. Каталог: {model.versions?.catalog_version_id || 'нет данных'}.</p></details>
          </div>
        </div>
      </header>

      <section className="bg-white border rounded-2xl p-5" aria-label="Источник модели">
        <div className="flex flex-wrap justify-between gap-3">
          <div><h2 className="font-semibold">{model.participationLabel}</h2><details className="text-sm text-slate-600"><summary>Технические подробности модели</summary>{model.modelId} · {model.positionId}</details></div>
          <p className="max-w-md text-xs text-amber-700">{model.participationHint}</p>
        </div>
      </section>

      {(model.blockers.length > 0 || model.warnings.length > 0) && (
        <section className="bg-white border rounded-2xl p-5" aria-label="Ограничения расчёта">
          <h2 className="font-semibold mb-3">Ограничения и предупреждения</h2>
          {[...model.blockers, ...model.warnings].map((issue) => (
            <div key={`${issue.code}-${issue.message}`} className="border-l-4 border-amber-400 pl-3 py-1 mb-2">
              <p className="text-sm text-slate-600">{issueText(issue)}</p><details className="text-xs"><summary>Код проверки</summary>{issue.code}</details>
            </div>
          ))}
        </section>
      )}

      <section className="grid md:grid-cols-2 gap-4" aria-label="Парк и производительность">
        <ResultCard label="Рекомендованный парк" value={formatFleet(model.recommendedFleet)} />
        <ResultCard label={model.fleetMode === 'MANUAL' ? 'Выбранный парк · ручной ввод' : 'Выбранный парк'} value={formatFleet(model.selectedFleet)} />
        <ResultCard label="Номинальная производительность" value={formatServerQuantity(model.nominalCapacity)} />
        <ResultCard label="Эффективная производительность" value={formatServerQuantity(model.effectiveCapacity)} />
        <ResultCard label="Покрытие" value={formatServerQuantity(model.coverage)} hint="Доля требуемого объёма работ, которую покрывает выбранный парк." />
        <ResultCard label="Фактическая загрузка" value={formatServerQuantity(model.rawLoadRatio)} hint="Требуемая нагрузка относительно доступной мощности; более 100 % означает перегрузку." />
        <ResultCard label="Отображаемая утилизация" value={formatServerQuantity(model.utilization)} hint="Загрузка для показа, ограниченная 100 %; число роботов указано отдельно." />
        <ResultCard label="Перегрузка" value={model.overloaded == null ? '—' : model.overloaded ? 'Да' : 'Нет'} />
      </section>

      <section className="bg-slate-50 border rounded-2xl p-5" aria-label="Экономический результат">
        <h2 className="font-semibold">Экономика</h2><p className="text-sm text-slate-600">{model.economicsLabel}</p>
      </section>

      <section className="bg-white border rounded-2xl p-5" aria-label="Трассировка расчёта">
        <h2 className="font-semibold">Как получен результат</h2>
        <p className="text-xs text-slate-500 mb-3">Показаны серверные шаги и источники. Интерфейс не пересчитывает формулы.</p>
        {model.steps.length === 0 ? <p className="text-sm text-slate-500">Вычислительные шаги отсутствуют: расчёт остановлен до формул.</p> : model.steps.map((step) => (
          <details key={step.id} className="border rounded-xl p-3 mb-2">
            <summary className="cursor-pointer font-medium">{step.formulaId} · {step.title}</summary>
            <p className="text-xs text-slate-500 mt-1">Версия {step.version} · {step.sourceRefs.join(', ')}</p>
            {step.inputs.map((input) => <p key={input.name} className="text-sm mt-2"><code>{input.name}</code>: {input.value}<span className="block text-xs text-slate-500">Источник: {input.source}</span></p>)}
            {step.outputs.map((output) => <p key={output.name} className="text-sm mt-2"><code>{output.name}</code>: {formatServerQuantity(output.value)}</p>)}
          </details>
        ))}
        {model.assumptions.length > 0 && <details className="border rounded-xl p-3 mb-2">
          <summary className="cursor-pointer font-medium">Допущения ({model.assumptions.length})</summary>
          {model.assumptions.map((item) => <p key={item.assumption_id} className="text-sm mt-2"><code>{item.assumption_id}</code>: {item.rationale}<span className="block text-xs text-slate-500">{item.mode} · {item.confirmation_state}</span></p>)}
        </details>}
        {model.constraints.length > 0 && <details className="border rounded-xl p-3 mb-2">
          <summary className="cursor-pointer font-medium">Проверки применимости ({model.constraints.length})</summary>
          {model.constraints.map((item) => <p key={item.evaluation_id} className="text-sm mt-2"><code>{item.check_id}</code>: {item.status}<span className="block text-xs text-slate-500">{item.reason_code}</span></p>)}
        </details>}
        <details className="border rounded-xl p-3">
          <summary className="cursor-pointer font-medium">Версии сохранённого расчёта</summary>
          {Object.entries(model.versions || {}).map(([name, value]) => <p key={name} className="text-xs mt-2 break-all"><code>{name}</code>: {value}</p>)}
        </details>
      </section>

      {onRestart && <button type="button" className="secondary-action" onClick={onRestart}>Новый расчёт</button>}
    </main>
  );
}

function ResultCard({ label, value, hint }) {
  return <article className="bg-white border rounded-xl p-4"><p className="text-xs text-slate-500">{label}</p><p className="text-xl font-semibold mt-1">{value}</p>{hint && <p className="text-xs text-slate-500 mt-2">{hint}</p>}</article>;
}
