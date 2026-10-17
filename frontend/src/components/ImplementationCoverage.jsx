import { formatServerMoney } from '../commercialScenariosModel';

const LABELS = { DELIVERY: 'Доставка', COMMISSIONING: 'Пусконаладка', INTEGRATION: 'Интеграция' };

export default function ImplementationCoverage({ coverage }) {
  if (!coverage) return null;
  return <section className="economics-inputs-v2 rounded-2xl border border-amber-300 p-5" aria-label="Покрытие расходов внедрения">
    <h2 className="text-xl font-semibold">Расходы внедрения</h2>
    <p>Известная сумма: <strong>{formatServerMoney(coverage.known_subtotal_gross_rub)}</strong>. {coverage.status === 'COMPLETE'
      ? 'Все обязательные статьи имеют явный статус.'
      : 'Это частичная сумма. NPV и окупаемость покупки ждут неизвестные статьи.'}</p>
    <p className="text-xs break-words">Дата оценки: {coverage.evaluation_date || 'не указана'} · ревизия ввода: {coverage.input_revision || 'не указана'} · расчёт: {coverage.run_id || 'не указан'}</p>
    <div className="mt-3 grid gap-3 md:grid-cols-3">{Object.entries(coverage.lines || {}).map(([category, line]) =>
      <article className="rounded border p-3" key={category}>
        <h3 className="font-semibold">{LABELS[category] || category}</h3>
        <p>{line.status === 'UNKNOWN' ? 'Неизвестно' : line.status === 'EXPLICIT_ZERO' ? 'Подтверждённый ноль' : line.status === 'NOT_APPLICABLE'
          ? 'Не применяется' : line.status === 'INCLUDED' ? 'Включено в прочие работы' : formatServerMoney(line.amount)}</p>
        <small>{line.source_ref || line.explanation || 'Источник не указан'}</small>
      </article>)}</div>
  </section>;
}
