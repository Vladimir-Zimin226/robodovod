import demo from '../warehouseGuestDemo.json' with { type: 'json' };
import assumptions from '../../../data/scenarios/warehouse-economics-demo-v1.json' with { type: 'json' };
import { formatServerMoney } from '../commercialScenariosModel';
import { formatServerQuantity } from '../capacityResultsModel';
import { formatFleet } from '../displayNumber';

const acquisitionLabel = { PURCHASE: 'Покупка', RAAS: 'RaaS' };
const uncertaintyLabel = { PESSIMISTIC: 'Пессимистичный', BASE: 'Базовый', OPTIMISTIC: 'Оптимистичный' };

export default function GuestWarehouseDemo({ onContinue, onBack }) {
  const base = demo.scenarios.filter((item) => item.uncertainty === 'BASE');
  const baseline = base[0]?.annual_ledgers?.[0]?.primary_cf_base;
  return <main className="mx-auto max-w-6xl space-y-5 p-5" aria-label="Гостевое демо склада">
    <header className="rounded-2xl border bg-white p-5">
      <p className="text-xs text-slate-500">{demo.schema_version} · фиксированный пример от {demo.as_of}</p>
      <h1 className="text-2xl font-semibold">Демо склада без регистрации</h1>
      <p>{demo.process}</p>
      <p className="mt-2 text-sm text-amber-800">{demo.model_notice}. Это заранее вычисленный пример; ваши данные сюда не вводятся и на сервер не отправляются.</p>
      <p className="text-xs mt-2">Набор условий: {demo.assumptions_version}. Исходные расчёты воспроизводятся скриптом {demo.source}.</p>
    </header>
    <section className="grid gap-3 md:grid-cols-3" aria-label="Технический результат C11">
      <article className="rounded-xl border bg-white p-4"><h2 className="font-semibold">Парк C11</h2><strong>{formatFleet(demo.capacity.value.selected_fleet)}</strong></article>
      <article className="rounded-xl border bg-white p-4"><h2 className="font-semibold">Эффективная мощность</h2><strong>{formatServerQuantity(demo.capacity.value.effective_capacity)}</strong></article>
      <article className="rounded-xl border bg-white p-4"><h2 className="font-semibold">Покрытие нагрузки</h2><strong>{formatServerQuantity(demo.capacity.value.coverage)}</strong></article>
    </section>
    <section className="rounded-xl border bg-white p-4" aria-label="Экономика демо">
      <h2 className="text-xl font-semibold">Baseline, покупка и RaaS</h2>
      <p>Денежный поток без роботов за первый год: {formatServerMoney(baseline)}. Ниже сохранённые NPV проекта для шести сценариев.</p>
      <div className="mt-3 grid gap-3 md:grid-cols-3">{demo.scenarios.map((item) => <article key={`${item.acquisition}:${item.uncertainty}`} className="rounded border p-3">
        <h3 className="font-semibold">{acquisitionLabel[item.acquisition]} · {uncertaintyLabel[item.uncertainty]}</h3>
        <p>NPV: {item.npv_project.status === 'COMPLETE' ? formatServerMoney(item.npv_project.value) : 'не рассчитано'}</p>
      </article>)}</div>
      <p className="mt-3 text-sm text-amber-800">C05: {demo.c05} · Закупка: {demo.procurement}. Положительный NPV не подтверждает пригодность, цену или доступность модели.</p>
    </section>
    <section className="rounded-xl border bg-white p-4" aria-label="Чувствительность демо">
      <h2 className="font-semibold">Чувствительность</h2>
      <p>Изменение NPV при тестовых отклонениях цены, объёма и зарплаты ±10 %; значения взяты из сохранённого расчётного примера.</p>
      <ul className="mt-2 grid gap-2 md:grid-cols-2">{demo.sensitivity.map((item) => <li key={item.variant_id} className="rounded border p-2">
        {item.override.parameter_id} · {item.override.direction}: {item.status === 'BLOCKED' ? 'не рассчитано' : formatServerMoney(item.npv_project.delta_value)}
      </li>)}</ul>
    </section>
    <details className="rounded-xl border bg-white p-4">
      <summary className="cursor-pointer font-semibold">Посмотреть все исходные допущения</summary>
      <p className="mt-2 text-sm">{assumptions.source}. Дата {assumptions.published_on}. Числа не являются фактическими условиями вашего объекта или поставщика.</p>
      <ul className="mt-2 grid gap-2 md:grid-cols-2">{Object.entries(assumptions.fields).map(([field, item]) => <li key={field} className="rounded border p-2 text-sm"><code>{field}</code>: {item.value} {item.unit}. {item.rationale}.</li>)}</ul>
    </details>
    <div className="flex flex-wrap gap-3">
      <button type="button" className="primary-action" onClick={onContinue}>Открыть ввод своего процесса и проект</button>
      <button type="button" className="secondary-action" onClick={onBack}>На главную</button>
    </div>
    <p className="text-xs text-slate-500">Проверочные SHA-256: вход {demo.input_digest}; результат {demo.result_digest}.</p>
  </main>;
}
