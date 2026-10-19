import { useState } from 'react';
import AppIcon from './AppIcon';
import RDAssistantWidget from './RDAssistantWidget';

const NAVIGATION = [
  { id: 'home', label: 'Главная', icon: 'home' },
  { id: 'demo', label: 'Готовый пример', icon: 'cube' },
  { id: 'calculation', label: 'Мой объект и расчёт', icon: 'calculator' },
  { id: 'results', label: 'Мой результат', icon: 'chart' },
];
const JOURNEY_NAVIGATION = [
  { id: 'home', label: 'Объект', icon: 'warehouse' },
  { id: 'calculation', label: 'Работа', icon: 'process' },
  { id: 'robots', label: 'Роботы', icon: 'cube' },
  { id: 'money', label: 'Деньги', icon: 'money' },
  { id: 'results', label: 'Результат', icon: 'chart' },
];
const GUIDE = {
  onboarding: ['Начнём с главного', 'Выберите объект. Пока не нужны названия моделей, формулы или смета.', 'Готовый пример можно посмотреть без регистрации.'],
  intake: ['Сначала задача', 'Выберите одну работу и укажите её объём. Расширенные параметры доступны ниже.', 'Для сохранения собственного расчёта нужен проект.'],
  robots: ['Что показано', 'Сначала смотрите расчётный парк и ограничения. Конкретная модель требует проверки на объекте.', 'Следующий шаг — стоимость.'],
  money: ['Неизвестное видно', 'Стоимость разделена на оборудование, внедрение и эксплуатацию. Пропущенная статья не становится нулём.', 'Можно сохранить частичный результат.'],
  results: ['Проверьте вывод', 'Результат показывает парк, доступные денежные ветки и недостающие данные.', 'Сохранённый расчёт можно открыть и уточнить позже.'],
};
const TOOL_NAVIGATION = [
  { id: 'economics', label: 'Справочник экономики', icon: 'money' },
  { id: 'report', label: 'Отчёты', icon: 'report' },
];

export function AppShell({ phase, user, activeProject, objectType, journeyMode, result, onNavigate, command, setCommand, onCommand, children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isResult = phase === 'results';
  const isJourney = Object.hasOwn(GUIDE, phase);
  const guide = phase === 'intake' && objectType === 'retail'
    ? ['Сначала все роли', 'Отметьте сотрудников склада и уточните численность, оплату и объём их работы.', 'После расчёта роботы появятся для каждой выбранной роли.']
    : GUIDE[phase];
  const activeNav = phase === 'onboarding' ? 'home' : phase === 'guestDemo' ? 'demo' : phase === 'intake' ? 'calculation' : phase === 'catalog' ? 'library' : phase === 'reports' ? 'report' : phase === 'economicsMethodology' ? 'economics' : phase;
  const initials = (user?.name || user?.email || 'Г')
    .split(/[\s@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');

  const navigate = (item) => {
    onNavigate(item);
    setMenuOpen(false);
  };

  return (
    <div className={`robodovod-app${isJourney ? ' is-simple-journey' : ''}`}>
      <button className="mobile-menu-button" onClick={() => setMenuOpen((open) => !open)} aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menuOpen}>
        <AppIcon name={menuOpen ? 'close' : 'menu'} />
      </button>
      {menuOpen && <button className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Закрыть меню" />}
      <aside className={`app-sidebar ${menuOpen ? 'is-open' : ''}`} aria-label="Основная навигация">
        <div className="brand-block">
          <div className="brand-identity">
            <strong className="brand-word" aria-label="РОБОДОВОД">РОБО<span>ДОВОД</span></strong>
          </div>
          <p>Больше, чем роботы.<br />Доводы до инвестиций.</p>
        </div>
        {isJourney && <p className="journey-nav-label">ВАШ ПУТЬ</p>}
        <nav className={`app-nav${isJourney ? ' journey-nav' : ''}`}>
          {(isJourney ? JOURNEY_NAVIGATION : NAVIGATION).map((item, index) => (
            <button key={item.id} onClick={() => navigate(item)} className={item.id === activeNav ? 'active' : ''} aria-current={item.id === activeNav ? 'step' : undefined}>
              {isJourney ? <span className="journey-nav-number">{index + 1}</span> : <AppIcon name={item.icon} />}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        {!isJourney && <details className="app-tool-nav" open={TOOL_NAVIGATION.some((item) => item.id === activeNav) ? true : undefined}>
          <summary>Дополнительные инструменты</summary>
          <nav className="app-nav" aria-label="Дополнительные инструменты">
            {TOOL_NAVIGATION.map((item) => <button key={item.id} onClick={() => navigate(item)} className={item.id === activeNav ? 'active' : ''} aria-current={item.id === activeNav ? 'page' : undefined}>
              <AppIcon name={item.icon} /><span>{item.label}</span>
            </button>)}
          </nav>
        </details>}
        <nav className="nav-secondary" aria-label="Проект и данные">
          {!isJourney && <button className={activeNav === 'templates' ? 'active' : ''} aria-current={activeNav === 'templates' ? 'page' : undefined} onClick={() => navigate({ id: 'templates' })}><AppIcon name="report" /><span>Шаблоны и загрузка данных</span></button>}
          {!isJourney && <button className={activeNav === 'library' ? 'active' : ''} aria-current={activeNav === 'library' ? 'page' : undefined} onClick={() => navigate({ id: 'library' })}><AppIcon name="library" /><span>Библиотека решений</span></button>}
          {user && <button className={activeNav === 'projects' ? 'active' : ''} aria-current={activeNav === 'projects' ? 'page' : undefined} onClick={() => navigate({ id: 'projects' })}><AppIcon name="report" /><span>Мои проекты</span></button>}
        </nav>
        {user?.role === 'ADMIN' && <nav className="nav-secondary nav-admin" aria-label="Администрирование">
          <button className={activeNav === 'adminCatalog' ? 'active' : ''} aria-current={activeNav === 'adminCatalog' ? 'page' : undefined} onClick={() => navigate({ id: 'adminCatalog' })}><AppIcon name="library" /><span>Каталог и источники</span></button>
          <button className={activeNav === 'admin' ? 'active' : ''} aria-current={activeNav === 'admin' ? 'page' : undefined} onClick={() => navigate({ id: 'admin' })}><AppIcon name="process" /><span>Пользователи</span></button>
        </nav>}
        <div className="sidebar-footer">
          <div className="footer-brand"><span>РОБОДОВОД</span></div>
          <div>СЕГОДНЯ<br /><strong>АНАЛИЗ.</strong><br />ЗАВТРА<br /><strong>ЭФФЕКТ.</strong></div>
          <p>Сделано для реального производства<br /><a href="https://www.zmncraft.ru/" target="_blank" rel="noreferrer">ZMNCRAFT</a></p>
        </div>
      </aside>
      <div className="app-workspace">
        <header className={`command-header${isJourney ? ' journey-header' : ''}`}>
          <form onSubmit={onCommand} className="command-form" role="search">
            <AppIcon name="search" />
            <label className="sr-only" htmlFor="process-command">Какой процесс вы хотите автоматизировать?</label>
            <input id="process-command" value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Какой процесс вы хотите автоматизировать?" />
            <button type="submit" aria-label="Перейти к описанию процесса"><AppIcon name="arrow" /></button>
          </form>
          <div className="project-context">
            <AppIcon name="cube" />
            <div><strong>{activeProject?.name || (user ? 'Проект не выбран' : isResult ? 'Текущий расчёт' : 'Гостевой расчёт')}</strong><span>{activeProject ? 'Сохраняемый проект' : user ? 'Выберите проект для v2' : isResult ? 'Предварительное ТЭО' : 'Россия'}</span></div>
          </div>
          <button className={`user-avatar ${activeNav === 'account' ? 'active' : ''}`} onClick={() => navigate({ id: 'account' })} aria-label={user ? `Аккаунт ${user.email}` : 'Войти или зарегистрироваться'} title={user ? user.email : 'Войти'}>{initials}</button>
          <button type="button" className="mobile-account-action" onClick={() => navigate({ id: user ? 'account' : 'register' })}>
            {user ? 'Мой аккаунт' : 'Войти / регистрация'}
          </button>
          <p className="command-examples">Например: «Перемещение паллет на складе», «Упаковка готовой продукции», «Подача материалов на линию»</p>
        </header>
        <div className={`app-stage${isJourney ? ' with-guide' : ''}`}>
          <div className="app-content" style={isResult ? { overflowAnchor: 'none' } : undefined}>{children}</div>
          {isJourney && <aside className="journey-guide" aria-label="Подсказка по текущему шагу">
            <p className="journey-guide-label">ВАШ ЦИФРОВОЙ ИНЖЕНЕР</p>
            <div className="journey-guide-card"><span className="journey-guide-icon"><AppIcon name="assistant" size={25} /></span>
              <h2>{guide[0]}</h2><p>{guide[1]}</p><small>{guide[2]}</small>
              <button type="button" onClick={() => window.dispatchEvent(new Event('robodovod:open-help'))}>Задать вопрос <AppIcon name="arrow" size={16} /></button>
            </div>
            <div className="journey-guide-status"><h3>Состояние оценки</h3>
              <p><span>Объект</span><strong>{({ retail: 'Склад', airport: 'Аэропорт', clinic: 'Клиника' })[objectType] || 'Не выбран'}</strong></p>
              <p><span>Режим</span><strong>{({ FAMILIAR: 'Ознакомиться', ADVANCED: 'Свой объект', FULL: 'Полная оценка' })[journeyMode] || 'Свой объект'}</strong></p>
              <p><span>Результат</span><strong>{result ? 'Есть сохранённый расчёт' : 'Пока нет'}</strong></p>
            </div>
          </aside>}
        </div>
      </div>
      <RDAssistantWidget />
    </div>
  );
}
