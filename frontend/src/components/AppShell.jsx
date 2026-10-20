import { useState } from 'react';
import AppIcon from './AppIcon';
import RDAssistantWidget from './RDAssistantWidget';

const NAVIGATION = [
  { id: 'home', label: 'Главная', icon: 'home' },
  { id: 'economics', label: 'Справочник экономики', icon: 'money' },
  { id: 'library', label: 'Библиотека решений', icon: 'library' },
];
const JOURNEY_NAVIGATION = [
  { id: 'calculation', label: 'Работа', icon: 'process' },
  { id: 'robots', label: 'Роботы', icon: 'cube' },
  { id: 'simulation', label: 'Симуляция', icon: 'chart' },
  { id: 'money', label: 'Деньги', icon: 'money' },
  { id: 'results', label: 'Результат', icon: 'chart' },
];
export function AppShell({ phase, user, activeProject, onNavigate, command, setCommand, onCommand, children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isResult = phase === 'results';
  const isJourney = ['intake', 'robots', 'simulation', 'money', 'results'].includes(phase);
  const activeNav = phase === 'onboarding' ? 'home' : phase === 'intake' ? 'calculation' : phase === 'catalog' ? 'library' : phase === 'reports' ? 'report' : phase === 'economicsMethodology' ? 'economics' : phase;
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
          <p>Больше, чем роботы.<br />Доводы для инвестиций.</p>
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
        <nav className="nav-secondary" aria-label="Проект и данные">
          {isJourney && NAVIGATION.map((item) => <button key={item.id} onClick={() => navigate(item)}><AppIcon name={item.icon} /><span>{item.label}</span></button>)}
          {user && <button onClick={() => navigate({ id: 'craft' })}><AppIcon name="cube" /><span>Конструктор объекта</span></button>}
          {user && <button className={activeNav === 'projects' ? 'active' : ''} aria-current={activeNav === 'projects' ? 'page' : undefined} onClick={() => navigate({ id: 'projects' })}><AppIcon name="report" /><span>Проекты</span></button>}
          {user && <button className={activeNav === 'report' ? 'active' : ''} onClick={() => navigate({ id: 'report' })}><AppIcon name="report" /><span>Отчёты</span></button>}
        </nav>
        {user?.role === 'ADMIN' && <nav className="nav-secondary nav-admin" aria-label="Администрирование">
          <button className={activeNav === 'adminCatalog' ? 'active' : ''} aria-current={activeNav === 'adminCatalog' ? 'page' : undefined} onClick={() => navigate({ id: 'adminCatalog' })}><AppIcon name="library" /><span>Версии каталога</span></button>
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
        </div>
      </div>
      <RDAssistantWidget user={user} />
    </div>
  );
}
