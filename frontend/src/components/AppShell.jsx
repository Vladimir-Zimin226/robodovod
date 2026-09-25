import { useState } from 'react';
import AppIcon from './AppIcon';

const NAVIGATION = [
  { id: 'home', label: 'Главная', icon: 'home' },
  { id: 'process', label: 'Помощник по сервису', icon: 'process' },
  { id: 'calculation', label: 'Расчёт', icon: 'calculator' },
  { id: 'model', label: 'Моделирование процесса', icon: 'cube' },
  { id: 'expert', label: 'Робоэксперт', icon: 'chart' },
  { id: 'economics', label: 'Экономика', icon: 'money', target: 'economics' },
  { id: 'report', label: 'Отчёт', icon: 'report', target: 'report' },
];

export function AppShell({ phase, user, activeProject, onNavigate, command, setCommand, onCommand, children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isResult = phase === 'results';
  const activeNav = phase === 'onboarding' ? 'home' : phase === 'intake' ? 'calculation' : phase === 'catalog' ? 'library' : phase === 'reports' ? 'report' : phase;
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
    <div className="robodovod-app">
      <button className="mobile-menu-button" onClick={() => setMenuOpen((open) => !open)} aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menuOpen}>
        <AppIcon name={menuOpen ? 'close' : 'menu'} />
      </button>
      {menuOpen && <button className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Закрыть меню" />}
      <aside className={`app-sidebar ${menuOpen ? 'is-open' : ''}`} aria-label="Основная навигация">
        <div className="brand-block">
          <div className="brand-word">РОБО<span>ДОВОД</span></div>
          <p>Больше, чем роботы.<br />Доводы до инвестиций.</p>
        </div>
        <nav className="app-nav">
          {NAVIGATION.map((item) => (
            <button key={item.id} onClick={() => navigate(item)} className={item.id === activeNav ? 'active' : ''} aria-current={item.id === activeNav ? 'page' : undefined}>
              <AppIcon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="nav-secondary">
          <button className={activeNav === 'library' ? 'active' : ''} aria-current={activeNav === 'library' ? 'page' : undefined} onClick={() => navigate({ id: 'library' })}><AppIcon name="library" /><span>Библиотека решений</span></button>
          {user && <button className={activeNav === 'projects' ? 'active' : ''} onClick={() => navigate({ id: 'projects' })}><AppIcon name="report" /><span>Мои проекты</span></button>}
          {user?.role === 'ADMIN' && <button className={activeNav === 'admin' ? 'active' : ''} onClick={() => navigate({ id: 'admin' })}><AppIcon name="process" /><span>Пользователи</span></button>}
        </div>
        <div className="sidebar-footer">
          <div>СЕГОДНЯ<br /><strong>АНАЛИЗ.</strong><br />ЗАВТРА<br /><strong>ЭФФЕКТ.</strong></div>
          <p>v1.0<br />Сделано для реального производства</p>
        </div>
      </aside>
      <div className="app-workspace">
        <header className="command-header">
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
          <p className="command-examples">Например: «Перемещение паллет на складе», «Упаковка готовой продукции», «Подача материалов на линию»</p>
        </header>
        <div className="app-content">{children}</div>
      </div>
    </div>
  );
}
