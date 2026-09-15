import { useState } from 'react';
import AppIcon from './AppIcon';

const NAVIGATION = [
  { id: 'home', label: 'Главная', icon: 'home' },
  { id: 'process', label: 'Процесс', icon: 'process' },
  { id: 'model', label: 'Моделирование', icon: 'cube', target: 'visualization' },
  { id: 'variants', label: 'Варианты', icon: 'chart', target: 'scenarios' },
  { id: 'economics', label: 'Экономика', icon: 'money', target: 'economics' },
  { id: 'report', label: 'Отчёт', icon: 'report', target: 'report' },
];

export function AppShell({ phase, onNavigate, command, setCommand, onCommand, children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isResult = phase === 'results';
  const activeNav = phase === 'onboarding' ? 'home' : phase === 'intake' ? 'process' : phase === 'catalog' ? 'library' : 'home';

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
            <button key={item.id} onClick={() => navigate(item)} className={item.id === activeNav ? 'active' : ''}>
              <AppIcon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="nav-secondary">
          <button className={activeNav === 'library' ? 'active' : ''} onClick={() => navigate({ id: 'library' })}><AppIcon name="library" /><span>Библиотека решений</span></button>
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
            <div><strong>{isResult ? 'Текущий расчёт' : 'Новый проект'}</strong><span>{isResult ? 'Предварительное ТЭО' : 'Россия'}</span></div>
          </div>
          <div className="user-avatar" aria-label="Локальный пользователь">ВК</div>
          <p className="command-examples">Например: «Перемещение паллет на складе», «Упаковка готовой продукции», «Подача материалов на линию»</p>
        </header>
        <div className="app-content">{children}</div>
      </div>
    </div>
  );
}
