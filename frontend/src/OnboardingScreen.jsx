import { useState } from 'react';
import AppIcon from './components/AppIcon';
import demo from './warehouseGuestDemo.json' with { type: 'json' };
import comparison from './warehouseGuestComparisonV1.json' with { type: 'json' };
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
  const [load, setLoad] = useState('base');
  const shown = load === 'base' ? demo : comparison.demo;
  return <div className="landing-preview" role="group" aria-label="Два рассчитанных примера условного склада">
    <div className="landing-preview-top"><span className="landing-live-dot" /> СКЛАД · ПЕРЕВОЗКА ПАЛЛЕТ <span className="landing-preview-code">ДЕМО</span></div>
    <div className="landing-preview-switch" role="group" aria-label="Нагрузка демонстрационного склада">
      <button type="button" aria-pressed={load === 'base'} onClick={() => setLoad('base')}>2 000 / сутки</button>
      <button type="button" aria-pressed={load === 'peak'} onClick={() => setLoad('peak')}>2 400 / сутки</button>
    </div>
    <div className="landing-route" aria-hidden="true">
      <svg viewBox="0 0 520 296" role="presentation" focusable="false">
        <defs>
          <pattern id="landing-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#26454a" strokeWidth="1" /></pattern>
          <linearGradient id="landing-floor" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#16343a" /><stop offset="1" stopColor="#0a1b22" /></linearGradient>
          <linearGradient id="landing-rack" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#456456" /><stop offset="1" stopColor="#203d38" /></linearGradient>
        </defs>
        <rect x="1" y="1" width="518" height="294" rx="12" fill="url(#landing-floor)" />
        <rect x="1" y="1" width="518" height="294" rx="12" fill="url(#landing-grid)" />
        <rect x="18" y="22" width="484" height="244" rx="6" fill="none" stroke="#5a7772" strokeWidth="4" />
        <rect x="32" y="37" width="109" height="205" rx="4" fill="#1b3436" stroke="#54776a" />
        {[0, 1, 2, 3].map((row) => <g key={row}>
          <rect x="46" y={49 + row * 48} width="82" height="28" rx="3" fill="url(#landing-rack)" stroke="#91ad77" />
          <path d={`M48 ${59 + row * 48}h78 M48 ${68 + row * 48}h78`} stroke="#a4be91" opacity=".7" />
          <path d={`M146 ${63 + row * 48} H450`} stroke="#4bd0cd" strokeWidth="2" strokeDasharray="7 8" opacity=".6" />
          <circle cx="443" cy={63 + row * 48} r="5" fill="#efc075" />
          <g className="landing-amr" style={{ animationDelay: `${-row * 1.8}s` }}>
            <rect x="153" y={52 + row * 48} width="25" height="21" rx="6" fill="#9ff555" stroke="#d5ff99" strokeWidth="2" />
            <rect x="160" y={48 + row * 48} width="11" height="7" rx="1" fill="#d8a45a" />
          </g>
        </g>)}
        <rect x="467" y="39" width="21" height="204" rx="3" fill="#233b3c" stroke="#647e78" />
        <text x="42" y="257">СТЕЛЛАЖИ</text><text x="355" y="257">ОТГРУЗКА</text>
        <text x="270" y="30" textAnchor="middle">УСЛОВНЫЙ ПЛАН · ДВИЖЕНИЕ ИЛЛЮСТРАТИВНОЕ</text>
      </svg>
    </div>
    <div className="landing-preview-metrics">
      <div><span>Расчётный парк</span><strong>{formatFleet(shown.capacity.value.selected_fleet)}</strong></div>
      <div><span>Эффективная мощность</span><strong>{formatServerQuantity(shown.capacity.value.effective_capacity)}</strong></div>
      <div><span>Покрытие нагрузки</span><strong>{formatServerQuantity(shown.capacity.value.coverage)}</strong></div>
    </div>
    <p className="landing-preview-note">Два сохранённых расчёта · {shown.as_of} · движение условное · пригодность и закупка не подтверждены</p>
  </div>;
}

export default function OnboardingScreen({ onChoose, onGuestDemo, onOwnProcess, onOpenCatalog }) {
  return <main className="onboarding-screen landing-page">
    <div className="landing-shell">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <p className="landing-eyebrow"><span className="landing-eyebrow-line" /> РОБОДОВОД · ПРЕДВАРИТЕЛЬНАЯ ОЦЕНКА</p>
          <h1 id="landing-title">Увидьте работу робота <span>до решения о покупке</span></h1>
          <p className="landing-lead">Покажем, как меняется работа склада при росте нагрузки: маршруты, потребный парк и денежный результат. Затем поможем проверить ваш процесс и условия объекта.</p>
          <div className="landing-actions">
            <button type="button" className="landing-button landing-button-primary" onClick={onGuestDemo}>Смотреть два сценария <AppIcon name="arrow" size={18} /></button>
            <button type="button" className="landing-button landing-button-secondary" onClick={onOwnProcess}>Описать свой объект <AppIcon name="arrow" size={18} /></button>
          </div>
          <p className="landing-entry-note">Демо открывается без регистрации. Свой процесс можно ввести в разделе «Расчёт»; для сохранения результата понадобится проект.</p>
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
