import AppIcon from './components/AppIcon';
import TrailerPlayer from './components/TrailerPlayer';

const OBJECTS = [
  { id: 'retail', icon: 'warehouse', title: 'Склад', detail: 'Перевозка паллет, уборка, комплектовка', note: 'Рассчитать склад по ролям · 8 видов работы' },
  { id: 'airport', icon: 'airport', title: 'Аэропорт', detail: 'Терминал, багаж и сервисные зоны', note: 'Рассчитать аэропорт по ролям · 13 видов работы' },
  { id: 'clinic', icon: 'clinic', title: 'Клиника', detail: 'Внутренняя доставка и уборка', note: 'Рассчитать клинику по ролям · 14 видов работы' },
];

export default function OnboardingScreen({ onChoose, onExample }) {
  return <main className="simple-journey-page" aria-label="Главная">
    <header className="simple-journey-head"><span>РОБОДОВОД</span>
      <h1>Больше, чем роботы.<br /><em>Доводы для инвестиций.</em></h1>
      <p>Оцените роботизацию на реальных расчётах. Начните с типа объекта.</p>
    </header>
    <section className="simple-journey-section" aria-label="Тип объекта">
      <h2>Выберите объект</h2>
      <div className="simple-object-grid">{OBJECTS.map((item) =>
        <button type="button" key={item.id} className={`simple-object-${item.id}`} onClick={() => onChoose(item.id)}>
          <span className="simple-object-icon"><AppIcon name={item.icon} size={36} /></span>
          <strong>{item.title}</strong><span>{item.detail}</span><small>{item.note}</small>
          <b>Оценить роботизацию <AppIcon name="arrow" size={17} /></b>
        </button>)}</div>
    </section>
    <section className="simple-journey-section" aria-label="Смотреть готовые примеры">
      <h2>Смотреть готовые примеры</h2><p>Типовые входные данные, допущения и ограничения открываются в той же форме оценки.</p>
      <div className="simple-object-grid">{OBJECTS.map((item) => <button type="button" key={item.id} onClick={() => onExample(item.id)}><AppIcon name={item.icon} size={30} /><strong>{item.title}</strong><span>Открыть пример</span></button>)}</div>
    </section>
    <TrailerPlayer />
  </main>;
}
