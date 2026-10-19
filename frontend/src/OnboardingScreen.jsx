import AppIcon from './components/AppIcon';
import demo from './warehouseGuestDemo.json' with { type: 'json' };
import comparison from './warehouseGuestComparisonV1.json' with { type: 'json' };

const OBJECTS = [
  { id: 'retail', icon: 'warehouse', title: 'Склад', detail: 'Перевозка паллет, уборка, комплектовка', note: 'Рассчитать склад по ролям · 8 видов работы' },
  { id: 'airport', icon: 'airport', title: 'Аэропорт', detail: 'Терминал, багаж и сервисные зоны', note: 'Рассчитать аэропорт по ролям · 13 видов работы' },
  { id: 'clinic', icon: 'clinic', title: 'Клиника', detail: 'Внутренняя доставка и уборка', note: 'Рассчитать клинику по ролям · 14 видов работы' },
];

const MODES = [
  { id: 'FAMILIAR', label: 'Ознакомиться', detail: 'Готовый пример' },
  { id: 'ADVANCED', label: 'Оценить свой объект', detail: 'Главные параметры' },
  { id: 'FULL', label: 'Полная оценка', detail: 'Смета и источники' },
];

export default function OnboardingScreen({ onChoose, onGuestDemo, mode = 'ADVANCED', onModeChange }) {
  const baseFleet = demo.capacity?.value?.selected_fleet;
  const peakFleet = comparison.demo?.capacity?.value?.selected_fleet;
  return <main className="simple-journey-page" aria-label="Выбор объекта и глубины оценки">
    <header className="simple-journey-head"><span>ШАГ 1 ИЗ 5 · ОБЪЕКТ</span>
      <h1>Где хотите использовать роботов?</h1>
      <p>Выберите объект и сразу перейдите к расчёту по всем его ролям. Для сохранения результата выберите или создайте проект. Прежний расчёт по отдельным операциям доступен на следующем экране.</p>
    </header>
    <section className="simple-journey-section" aria-label="Глубина оценки">
      <h2>Насколько подробно оценивать?</h2>
      <div className="simple-modebar" role="group" aria-label="Глубина оценки">{MODES.map((item) =>
        <button type="button" key={item.id} aria-pressed={mode === item.id} onClick={() => onModeChange?.(item.id)}>
          <strong>{item.label}</strong><small>{item.detail}</small>
        </button>)}</div>
      <p className="simple-hint">Глубину можно изменить позже. Неподтверждённые данные останутся неизвестными.</p>
    </section>
    <section className="simple-journey-section" aria-label="Тип объекта">
      <h2>Выберите объект</h2>
      <div className="simple-object-grid">{OBJECTS.map((item) =>
        <button type="button" key={item.id} onClick={() => onChoose(item.id)}>
          <span className="simple-object-icon"><AppIcon name={item.icon} size={36} /></span>
          <strong>{item.title}</strong><span>{item.detail}</span><small>{item.note}</small>
          <b>Рассчитать {item.title.toLowerCase()} по ролям <AppIcon name="arrow" size={17} /></b>
        </button>)}</div>
    </section>
    <section className="simple-demo-callout" aria-label="Готовый пример склада">
      <div><span className="simple-demo-eyebrow">ПОСМОТРЕТЬ БЕЗ РЕГИСТРАЦИИ</span>
        <h2>Готовый пример: склад</h2>
        <p>Два сохранённых расчёта одной операции: 2 000 и 2 400 паллет в сутки. Можно увидеть парк, деньги и схему движения, прежде чем вводить свои данные.</p>
        <button type="button" className="primary-action" onClick={onGuestDemo}>Открыть готовый пример <AppIcon name="arrow" size={18} /></button>
      </div>
      <div className="simple-demo-metrics"><div><strong>2 000</strong><span>паллет в сутки</span><b>{baseFleet ?? '—'} роботов</b></div><AppIcon name="arrow" size={25} /><div><strong>2 400</strong><span>паллет в сутки</span><b>{peakFleet ?? '—'} роботов</b></div></div>
    </section>
  </main>;
}
