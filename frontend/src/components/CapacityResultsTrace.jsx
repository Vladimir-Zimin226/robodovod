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
            <p className="text-sm text-slate-600 mt-1">Процесс: {zoneContext?.label || zoneForProcessId(model.processId)}</p>
            {model.processId?.includes('warehouse_receiving_shipping') && <p className="mt-1 text-sm text-amber-800">Учтена перевозка подготовленных паллет; отбор коробок и упаковка не рассчитаны. Экономия относится только к роли, связанной с перевозкой.</p>}
            <p className="text-xs text-slate-500">Зона: {zoneContext?.label || zoneForProcessId(model.processId)} · расчёт охватывает только указанный процесс и не суммирует общие ресурсы других зон.</p>
            {zoneContext?.constraints_note && <p className="text-xs text-amber-700">Ограничения зоны: {zoneContext.constraints_note} · не включены в проверку пригодности на объекте.</p>}
          </div>
          <div className="text-right">
            <span className="inline-flex rounded-full bg-blue-50 text-blue-700 px-3 py-1 text-sm font-semibold">{model.statusLabel}</span>
          </div>
        </div>
      </header>

      <section className="bg-white border rounded-2xl p-5" aria-label="Источник модели">
        <div className="flex flex-wrap justify-between gap-3">
          <div><h2 className="font-semibold">{model.participationLabel}</h2></div>
          <p className="max-w-md text-xs text-amber-700">{model.participationHint}</p>
        </div>
      </section>

      {(model.blockers.length > 0 || model.warnings.length > 0) && (
        <section className="bg-white border rounded-2xl p-5" aria-label="Ограничения расчёта">
          <h2 className="font-semibold mb-3">Ограничения и предупреждения</h2>
          {[...model.blockers, ...model.warnings].map((issue) => (
            <div key={`${issue.code}-${issue.message}`} className="border-l-4 border-amber-400 pl-3 py-1 mb-2">
              <p className="text-sm text-slate-600">{issueText(issue)}</p>
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

      {model.assumptions.length > 0 && <section className="bg-white border rounded-2xl p-5" aria-label="Допущения расчёта">
        <h2 className="font-semibold">Допущения</h2>
        <ul className="mt-2 list-disc pl-5">{model.assumptions.map((item) => <li key={item.assumption_id} className="text-sm mt-2">{humanizePresentation(item.rationale)}</li>)}</ul>
        <p className="text-xs text-slate-500 mt-3">Полная трассировка и версии сохранены в архиве расчёта.</p>
      </section>}

      {onRestart && <button type="button" className="secondary-action" onClick={onRestart}>Новый расчёт</button>}
    </main>
  );
}

function ResultCard({ label, value, hint }) {
  return <article className="bg-white border rounded-xl p-4"><p className="text-xs text-slate-500">{label}</p><p className="text-xl font-semibold mt-1">{value}</p>{hint && <p className="text-xs text-slate-500 mt-2">{hint}</p>}</article>;
}
