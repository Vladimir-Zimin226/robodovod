import EconomicsInputsV2 from './EconomicsInputsV2';
import { economicsFieldLabel } from '../economicsFieldLabels';
import { formatServerMoney } from '../commercialScenariosModel';

const BRANCHES = [
  ['capacity', 'Мощность C11'], ['labour', 'Труд C14'],
  ['purchase', 'Покупка C15–C16'], ['raas', 'RaaS C17'],
];

export default function PartialEconomicsResult({ result, run, project, onComplete }) {
  const branches = result.branches || {};
  return <div className="mx-auto max-w-6xl space-y-5" aria-label="Частичный результат экономики">
    <section className="economics-inputs-v2 rounded-2xl border p-5">
      <h2 className="text-xl font-semibold">Сохранён частичный расчёт</h2>
      <p>Неизвестные суммы и NPV отмечены «не рассчитано». Технический результат C11 сохранён отдельно.</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">{BRANCHES.map(([key, label]) => {
        const branch = branches[key] || {};
        return <article key={key} className="rounded border p-3">
          <h3 className="font-semibold">{label}</h3>
          <p>{branch.status === 'CALCULATED' || branch.status === 'AVAILABLE' ? 'Доступно' : 'Не рассчитано'}</p>
          {key === 'capacity' && branch.selected_fleet != null && <p>Выбранный парк: {branch.selected_fleet} роботов (предварительная оценка).</p>}
          {branch.required_fields?.length > 0 && <p>Далее укажите: {branch.required_fields.map(economicsFieldLabel).join(', ')}.</p>}
          {branch.required_fields?.some((field) => field.startsWith('role_pool')) && <p>Исправьте зарплату в «Процессах», сохраните новый C11 и начните экономику от него.</p>}
          {branch.reason_code === 'DOMAIN_INCOMPLETE' && <p>Проверьте входные данные этой ветки.</p>}
        </article>;
      })}</div>
      <p className="mt-3">C05: {result.c05?.eligibility || 'требуется проверка'} · Закупка не подтверждена. Рекомендация к закупке не сформирована.</p>
      {Object.entries(result.input_ranges || {}).length > 0 && <p className="mt-2">Сохранённые диапазоны (без подстановки в NPV): {Object.entries(result.input_ranges).map(([field, range]) => `${economicsFieldLabel(field)}: ${range.min}–${range.max}`).join('; ')}.</p>}
    </section>
    {result.scenarios?.length > 0 && <section className="economics-inputs-v2 rounded-2xl border p-5">
      <h3 className="font-semibold">Рассчитанные ветки</h3>
      <div className="mt-2 grid gap-2 md:grid-cols-3">{result.scenarios.map((scenario) => <article key={scenario.scenario_id} className="rounded border p-3">
        <strong>{scenario.acquisition} · {scenario.uncertainty}</strong>
        <p>NPV: {scenario.financial?.npv_project?.status === 'COMPLETE' ? formatServerMoney(scenario.financial.npv_project.value) : 'не рассчитано'}</p>
        <p>Закупка: {scenario.procurement?.procurement_status || 'не подтверждена'}</p>
      </article>)}</div>
    </section>}
    <EconomicsInputsV2 key={run?.id} capacityRequest={result.capacity_input} capacityRunId={result.capacity_run_id}
      project={project} initialInput={run?.input_snapshot?.economics} savedResult={result} onComplete={onComplete} />
  </div>;
}
