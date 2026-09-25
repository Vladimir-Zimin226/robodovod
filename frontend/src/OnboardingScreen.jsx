import AppIcon from './components/AppIcon';

const CARDS = [
  { type: 'retail', title: 'Торговля', sub: 'Склад', icon: 'cube' },
  { type: 'airport', title: 'Логистика', sub: 'Аэропорт', icon: 'process' },
  { type: 'clinic', title: 'Соц. сфера', sub: 'Медучреждение', icon: 'home' },
  { type: 'other', title: 'Другое', sub: 'Производственный объект', icon: 'chart' },
];

export default function OnboardingScreen({ onChoose, onGuestDemo }) {
  return (
    <div className="onboarding-screen min-h-full flex flex-col items-center justify-center p-8">
      <h1 className="text-3xl font-bold">РОБОДОВОД</h1>
      <p className="text-slate-500 mb-5 text-center">
        Предварительная оценка мощности, затрат и условий роботизации
      </p>
      <div className="mb-6 grid w-full max-w-5xl gap-4 md:grid-cols-2" aria-label="Как начать">
        <section className="rounded-2xl border border-blue-300 bg-white p-5">
          <h2 className="text-lg font-semibold">Посмотреть демо склада</h2>
          <p className="my-2 text-sm">Готовый расчёт паллетных перемещений: парк, baseline, покупка, RaaS и чувствительность. Откроется без регистрации и ввода ваших данных.</p>
          <button type="button" className="primary-action" onClick={onGuestDemo}>Открыть гостевое демо</button>
          <p className="mt-2 text-xs text-amber-800">Фиксированный пример с явными допущениями, C05 и закупка не подтверждены.</p>
        </section>
        <section className="rounded-2xl border border-blue-300 bg-white p-5">
          <h2 className="text-lg font-semibold">Рассчитать свой процесс</h2>
          <p className="my-2 text-sm">Выберите объект, внесите данные вручную или из файла и сохраните проект. Неизвестные поля дадут частичный результат без вымышленного NPV.</p>
          <button type="button" className="primary-action" onClick={() => onChoose('retail')}>Начать со склада и проекта</button>
          <p className="mt-2 text-xs text-slate-600">Технический C11 можно выполнить отдельно; экономика и условия закупки проверяются по своим данным.</p>
        </section>
      </div>
      <div className="grid w-full max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map((c) => (
          <div
            key={c.type}
            className="bg-white rounded-2xl border p-6 text-center hover:shadow-lg transition"
          >
            <div className="onboarding-icon"><AppIcon name={c.icon} size={30} /></div>
            <div className="font-semibold">{c.title}</div>
            <div className="text-sm text-slate-500 mb-4">{c.sub}</div>
            <button
              onClick={() => onChoose(c.type)}
              disabled={c.type === 'other'}
              className="w-full bg-blue-600 text-white rounded-xl py-2 text-sm mb-2"
            >
              {c.type === 'other' ? 'Расчёт пока недоступен' : 'Выбрать'}
            </button>
            {c.type === 'retail' && <p className="text-xs text-slate-500">Типовой склад доступен внутри формы v2.</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
