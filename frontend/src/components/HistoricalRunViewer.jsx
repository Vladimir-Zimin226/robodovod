import DashboardOverview from './DashboardOverview';
import ZonalDashboardOverview from './ZonalDashboardOverview';

export default function HistoricalRunViewer({ run, result, userInput, onNewCalculation }) {
  return <main className="mx-auto max-w-6xl space-y-5 p-5" aria-label="Исторический результат v1">
    <section className="rounded-xl border border-amber-400/50 bg-[#2b281d] p-4 text-sm">
      <h1 className="font-semibold">Исторический расчёт v1</h1>
      <p>Показаны сохранённые значения этого run. Для нового расчёта откройте маршрут v2; исходный snapshot и экспорт останутся неизменными.</p>
      <button type="button" className="primary-action mt-3" onClick={onNewCalculation}>Новый расчёт v2</button>
      {run?.id && <p className="mt-2 text-xs">Run: {run.id}</p>}
    </section>
    {result?.mode === 'zonal' ? <ZonalDashboardOverview result={result} />
      : <DashboardOverview result={result} userInput={userInput || {}} />}
    <details className="rounded-xl border p-4 text-sm">
      <summary className="cursor-pointer font-semibold">Исходные точные значения сохранённого результата</summary>
      <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(result, null, 2)}</pre>
    </details>
  </main>;
}
