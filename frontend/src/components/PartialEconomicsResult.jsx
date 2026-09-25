import SavedEconomicsEditor from './SavedEconomicsEditor';
import TechnicalVisualization from './TechnicalVisualization';
import { economicsFieldLabel } from '../economicsFieldLabels';
import { formatServerMoney } from '../commercialScenariosModel';
import { formatFleet } from '../displayNumber';
import { fieldPresentation, statusLabel, savedCalculationLabel } from '../presentation';

const BRANCHES = [
  ['capacity', 'Расчёт потребного парка'], ['labour', 'Расчёт труда'],
  ['purchase', 'Покупка роботов'], ['raas', 'Аренда роботов'],
];

export default function PartialEconomicsResult({ result, run, project, onComplete, autoOpenEditor = false }) {
  const branches = result.branches || {};
  return <div className="mx-auto max-w-6xl space-y-5" aria-label="Частичный результат экономики">
    <section className="economics-inputs-v2 rounded-2xl border p-5">
      <h2 className="text-xl font-semibold">Сохранён частичный расчёт</h2>
      <p>Неизвестные суммы и денежный эффект отмечены «не рассчитано». Расчёт потребного парка сохранён отдельно.</p>
      <p className="text-sm">{savedCalculationLabel(run?.finished_at || run?.created_at)}</p>
      <details><summary>Технические подробности</summary><p>Расчёт экономики: {run?.id || result.run_id}. Исходный расчёт парка: {result.capacity_run_id || 'не указан'}.</p></details>
      <div className="mt-3 grid gap-3 md:grid-cols-2">{BRANCHES.map(([key, label]) => {
        const branch = branches[key] || {};
        return <article key={key} className="rounded border p-3">
          <h3 className="font-semibold">{label}</h3>
          <p>{branch.status === 'CALCULATED' || branch.status === 'AVAILABLE' ? 'Доступно' : 'Не рассчитано'}</p>
          {key === 'capacity' && branch.selected_fleet != null && <p>Выбранный парк: {formatFleet(branch.selected_fleet)} (предварительная оценка).</p>}
          {branch.required_fields?.length > 0 && <details className="mt-2"><summary>Что уточнить: {branch.required_fields.length} условий</summary><ul className="mt-2 list-disc pl-5">{branch.required_fields.map((field) => <li key={field}><strong>{economicsFieldLabel(field)}</strong>: {fieldPresentation(field).action}</li>)}</ul></details>}
          {branch.required_fields?.some((field) => field.startsWith('role_pool')) && <p>Исправьте зарплату в «Процессах», сохраните новый расчёт парка и начните экономику от него.</p>}
          {branch.reason_code === 'DOMAIN_INCOMPLETE' && <p>Проверьте входные данные этой ветки.</p>}
        </article>;
      })}</div>
      <p className="mt-3">Проверка пригодности на объекте: {statusLabel(result.c05?.eligibility)} · Закупка не подтверждена. Рекомендация к закупке не сформирована.</p>
      {Object.entries(result.input_ranges || {}).length > 0 && <p className="mt-2">Сохранённые диапазоны (без расчёта денежного эффекта): {Object.entries(result.input_ranges).map(([field, range]) => `${economicsFieldLabel(field)}: ${range.min}–${range.max}`).join('; ')}.</p>}
    </section>
    {result.scenarios?.length > 0 && <section className="economics-inputs-v2 rounded-2xl border p-5">
      <h3 className="font-semibold">Рассчитанные ветки</h3>
      <div className="mt-2 grid gap-2 md:grid-cols-3">{result.scenarios.map((scenario) => <article key={scenario.scenario_id} className="rounded border p-3">
        <strong>{scenario.acquisition === 'PURCHASE' ? 'Покупка' : 'Аренда'} · {scenario.uncertainty === 'BASE' ? 'базовый' : scenario.uncertainty === 'PESSIMISTIC' ? 'осторожный' : 'оптимистичный'}</strong>
        <p>Чистая приведённая стоимость: {scenario.financial?.npv_project?.status === 'COMPLETE' ? formatServerMoney(scenario.financial.npv_project.value) : 'не рассчитано'}</p>
        <p>Закупка: {statusLabel(scenario.procurement?.procurement_status)}</p>
      </article>)}</div>
    </section>}
    <TechnicalVisualization run={run} />
    <SavedEconomicsEditor key={run?.id} project={project} run={run} autoOpen={autoOpenEditor} onComplete={onComplete} />
  </div>;
}
