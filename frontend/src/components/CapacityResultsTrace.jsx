import { useMemo } from 'react';
import { formatServerQuantity, getCapacityResultsModel } from '../dashboardModel';

const issueText = (issue) => issue.message || issue.code;

export default function CapacityResultsTrace({ response, expectedRevision = null, onRestart }) {
  const model = useMemo(
    () => getCapacityResultsModel(response, expectedRevision),
    [response, expectedRevision],
  );

  return (
    <main className="capacity-results-v2 max-w-6xl mx-auto p-6 space-y-5" aria-label="Результат расчёта производительности">
      <header className="bg-white border rounded-2xl p-5">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <p className="text-xs text-slate-500">Capacity snapshot · revision {model.revision}</p>
            <h1 className="text-2xl font-semibold">Производительность и требуемый парк</h1>
            <p className="text-sm text-slate-600 mt-1">Процесс: {model.processId}</p>
            <p className="text-xs text-slate-500 mt-1">Capacity source: {model.versions?.catalog_version_id || 'NOT_AVAILABLE'}</p>
          </div>
          <div className="text-right">
            <span className="inline-flex rounded-full bg-blue-50 text-blue-700 px-3 py-1 text-sm font-semibold">{model.statusLabel}</span>
            <p className="text-xs text-slate-500 mt-2">Run: {model.runId}</p>
          </div>
        </div>
      </header>

      <section className="bg-white border rounded-2xl p-5" aria-label="Источник модели">
        <div className="flex flex-wrap justify-between gap-3">
          <div><h2 className="font-semibold">{model.participationLabel}</h2><p className="text-sm text-slate-600">{model.modelId} · {model.positionId}</p></div>
          <p className="max-w-md text-xs text-amber-700">{model.participationHint}</p>
        </div>
      </section>

      {(model.blockers.length > 0 || model.warnings.length > 0) && (
        <section className="bg-white border rounded-2xl p-5" aria-label="Ограничения расчёта">
          <h2 className="font-semibold mb-3">Ограничения и предупреждения</h2>
          {[...model.blockers, ...model.warnings].map((issue) => (
            <div key={`${issue.code}-${issue.message}`} className="border-l-4 border-amber-400 pl-3 py-1 mb-2">
              <strong className="text-sm">{issue.code}</strong><p className="text-sm text-slate-600">{issueText(issue)}</p>
            </div>
          ))}
        </section>
      )}

      <section className="grid md:grid-cols-2 gap-4" aria-label="Парк и производительность">
        <ResultCard label="Рекомендованный парк" value={model.recommendedFleet == null ? '—' : `${model.recommendedFleet} robot`} />
        <ResultCard label={model.fleetMode === 'MANUAL' ? 'Выбранный парк · ручной ввод' : 'Выбранный парк'} value={model.selectedFleet == null ? '—' : `${model.selectedFleet} robot`} />
        <ResultCard label="Номинальная производительность" value={formatServerQuantity(model.nominalCapacity)} />
        <ResultCard label="Эффективная производительность" value={formatServerQuantity(model.effectiveCapacity)} />
        <ResultCard label="Покрытие" value={formatServerQuantity(model.coverage)} />
        <ResultCard label="Фактическая загрузка" value={formatServerQuantity(model.rawLoadRatio)} />
        <ResultCard label="Отображаемая утилизация" value={formatServerQuantity(model.utilization)} />
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
          <summary className="cursor-pointer font-medium">Версии snapshot</summary>
          {Object.entries(model.versions || {}).map(([name, value]) => <p key={name} className="text-xs mt-2 break-all"><code>{name}</code>: {value}</p>)}
        </details>
      </section>

      {onRestart && <button type="button" className="secondary-action" onClick={onRestart}>Новый расчёт</button>}
    </main>
  );
}

function ResultCard({ label, value }) {
  return <article className="bg-white border rounded-xl p-4"><p className="text-xs text-slate-500">{label}</p><p className="text-xl font-semibold mt-1">{value}</p></article>;
}
