import AppIcon from './components/AppIcon';
import demo from './warehouseGuestDemo.json' with { type: 'json' };
import { formatFleet } from './displayNumber';
import { formatServerQuantity } from './capacityResultsModel';
import './landing.css';

const OUTCOMES = [
  { number: '01', icon: 'library', title: 'Подбор с источниками',
    text: 'Сравните позиции активного каталога по одинаковым критериям. Пропуски и неподтверждённые характеристики остаются видимыми.' },
  { number: '02', icon: 'chart', title: 'Мощность и экономика',
    text: 'Узнайте предварительный парк и доступные ветки экономики. Демо-допущения, свои данные и неизвестные условия показаны отдельно.' },
  { number: '03', icon: 'cube', title: '2D-схема с KPI',
    text: 'Посмотрите условную работу роботов по маршруту и показатели симуляции, когда для неё хватает технических данных.' },
];

const STEPS = [
  ['Опишите процесс', 'Груз или операция, объём, график, маршрут и ограничения.'],
  ['Проверьте варианты', 'Сопоставьте характеристики и источники; подтвердите поля и допущения.'],
  ['Получите расчёт', 'Расчёт потребного парка и доступные варианты экономики показывают результат и недостающие данные.'],
  ['Изучите сценарий', 'Откройте схему процесса с показателями, затем сохраните расчёт и скачайте отчёт.'],
];

const FAQ = [
  ['Нужна ли регистрация для демо?', 'Нет. Гостевое демо склада открывается сразу и использует фиксированный пример. Для сохранения расчёта со своими данными нужен проект и вход в аккаунт.'],
  ['Можно ли считать без цены робота?', 'Да. Расчёт потребного парка не требует цены. Денежные варианты без коммерческих условий останутся частичными; чистая приведённая стоимость не подставляется автоматически.'],
  ['Что означает проверка пригодности?', 'Условия объекта и паспорт модели требуют отдельной проверки. Поставка и коммерческие условия также должны быть подтверждены поставщиком. Положительная экономика не заменяет эти проверки.'],
  ['Что показывает 2D?', 'Схему условного маршрута и показатели сохранённой симуляции процесса. Геометрия без плана объекта условна; это не телеметрия.'],
];

function WarehousePreview() {
  return <div className="landing-preview" role="group" aria-label="Пример результата условного склада">
    <div className="landing-preview-top"><span className="landing-live-dot" /> ПРИМЕР · УСЛОВНЫЙ СКЛАД <span className="landing-preview-code">РАСЧЁТ ПАРКА</span></div>
    <div className="landing-route" aria-hidden="true">
      <svg viewBox="0 0 390 158" role="presentation" focusable="false">
        <defs><pattern id="landing-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#254047" strokeWidth="1" /></pattern></defs>
        <rect x="1" y="1" width="388" height="156" rx="12" fill="url(#landing-grid)" />
        <rect x="28" y="31" width="71" height="93" rx="6" fill="#294038" stroke="#55785b" />
        <rect x="292" y="31" width="71" height="93" rx="6" fill="#294038" stroke="#55785b" />
        <path d="M100 79 H292" stroke="#4ccfe3" strokeWidth="3" strokeDasharray="7 6" fill="none" />
        <circle cx="103" cy="79" r="7" fill="#efb55f" stroke="#ffdf9d" />
        <circle cx="287" cy="79" r="7" fill="#4ccfe3" stroke="#b3f5f9" />
        <rect x="171" y="62" width="48" height="34" rx="8" fill="#93ed43" stroke="#c6ff83" strokeWidth="2" />
        <path d="M184 79h22m-5-5 5 5-5 5" stroke="#183022" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <text x="40" y="142">ПРИЁМКА</text><text x="299" y="142">ОТГРУЗКА</text>
      </svg>
    </div>
    <div className="landing-preview-metrics">
      <div><span>Предварительный парк</span><strong>{formatFleet(demo.capacity.value.selected_fleet)}</strong></div>
      <div><span>Эффективная мощность</span><strong>{formatServerQuantity(demo.capacity.value.effective_capacity)}</strong></div>
      <div><span>Покрытие нагрузки</span><strong>{formatServerQuantity(demo.capacity.value.coverage)}</strong></div>
    </div>
    <p className="landing-preview-note">Фиксированный пример от {demo.as_of} · пригодность требует проверки · закупка не подтверждена</p>
  </div>;
}

export default function OnboardingScreen({ onChoose, onGuestDemo, onOwnProcess, onOpenCatalog }) {
  return <main className="onboarding-screen landing-page">
    <div className="landing-shell">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <p className="landing-eyebrow"><span className="landing-eyebrow-line" /> РОБОДОВОД · ПРЕДВАРИТЕЛЬНАЯ ОЦЕНКА</p>
          <h1 id="landing-title">От процесса до <span>предварительного сценария</span> роботизации</h1>
          <p className="landing-lead">Для владельцев бизнеса, руководителей предприятий, операционных и финансовых директоров, руководителей автоматизации и специалистов объекта. Оцените потребный парк, денежные сценарии и вопросы, которые нужно проверить до решения о внедрении.</p>
          <div className="landing-actions">
            <button type="button" className="landing-button landing-button-primary" onClick={onGuestDemo}>Попробовать демо <AppIcon name="arrow" size={18} /></button>
            <button type="button" className="landing-button landing-button-secondary" onClick={onOwnProcess}>Рассчитать свой процесс <AppIcon name="arrow" size={18} /></button>
          </div>
          <p className="landing-entry-note">Демо открывается без регистрации. Свой процесс начинается с короткого интервью; для сохранения расчёта понадобится проект.</p>
          <button type="button" className="landing-catalog-link" onClick={onOpenCatalog}><AppIcon name="library" size={18} /> Смотреть каталог решений <AppIcon name="arrow" size={16} /></button>
        </div>
        <WarehousePreview />
      </section>

      <section className="landing-section landing-outcomes" aria-labelledby="landing-outcomes-title">
        <div className="landing-section-heading"><p className="landing-eyebrow">ЧТО ВЫ ПОЛУЧИТЕ</p><h2 id="landing-outcomes-title">Один маршрут — три ответа</h2></div>
        <div className="landing-outcome-grid">{OUTCOMES.map((outcome) => <article className="landing-outcome" key={outcome.number}>
          <div className="landing-outcome-top"><span>{outcome.number}</span><AppIcon name={outcome.icon} size={25} /></div>
          <h3>{outcome.title}</h3><p>{outcome.text}</p>
        </article>)}</div>
      </section>

      <section className="landing-section landing-method" aria-labelledby="landing-method-title">
        <div className="landing-section-heading"><p className="landing-eyebrow">КАК ЭТО РАБОТАЕТ</p><h2 id="landing-method-title">Четыре шага к предварительному сценарию</h2></div>
        <ol className="landing-steps">{STEPS.map(([title, text], index) => <li key={title}><span className="landing-step-number">0{index + 1}</span><h3>{title}</h3><p>{text}</p></li>)}</ol>
      </section>

      <section className="landing-section landing-contexts" aria-labelledby="landing-contexts-title">
        <div className="landing-section-heading"><p className="landing-eyebrow">СВОИ ДАННЫЕ</p><h2 id="landing-contexts-title">С чего начать расчёт</h2><p>Проверенный полный пример — паллетные перемещения на складе. Для других процессов результат зависит от доступной модели и полноты ввода.</p></div>
        <div className="landing-context-grid">
          <button type="button" onClick={() => onChoose('retail')}><AppIcon name="cube" size={22} /><span><strong>Склад</strong><small>Паллеты и уборка · типовой демо-профиль</small></span><AppIcon name="arrow" size={17} /></button>
          <button type="button" onClick={() => onChoose('airport')}><AppIcon name="process" size={22} /><span><strong>Аэропорт</strong><small>Процессы и роли v2 · доступность модели проверяется отдельно</small></span><AppIcon name="arrow" size={17} /></button>
          <button type="button" onClick={() => onChoose('clinic')}><AppIcon name="home" size={22} /><span><strong>Клиника</strong><small>Доставка и уборка · доступность модели проверяется отдельно</small></span><AppIcon name="arrow" size={17} /></button>
        </div>
      </section>

      <section className="landing-section landing-faq" aria-labelledby="landing-faq-title">
        <div className="landing-section-heading"><p className="landing-eyebrow">КОРОТКО О ГЛАВНОМ</p><h2 id="landing-faq-title">Частые вопросы</h2></div>
        <div>{FAQ.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div>
      </section>
      <footer className="landing-footer"><p>Результат — предварительная оценка по введённым данным и допущениям. Проверка объекта, модели и коммерческих условий остаётся необходимой.</p><button type="button" className="landing-button landing-button-primary" onClick={onGuestDemo}>Открыть демо склада <AppIcon name="arrow" size={18} /></button></footer>
    </div>
  </main>;
}
