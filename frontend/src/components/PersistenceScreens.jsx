import { useEffect, useState } from 'react';
import { persistenceRequest as request, readCsrfCookie } from '../persistenceApi';

export function AuthScreen({ user, onAuthenticated, onLoggedOut, onNavigate }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const payload = await request(`/api/auth/${mode === 'login' ? 'login' : 'register'}`, {
        method: 'POST',
        body: JSON.stringify(mode === 'login'
          ? { email: form.email, password: form.password }
          : form),
      });
      onAuthenticated(payload.user, payload.csrf_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    setBusy(true);
    setError('');
    try {
      await request('/api/auth/logout', {
        method: 'POST',
        headers: { 'X-CSRF-Token': readCsrfCookie() },
      });
      onLoggedOut();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (user) {
    return (
      <section className="persistence-screen narrow-screen">
        <div className="persistence-heading">
          <span className="eyebrow">УЧЁТНАЯ ЗАПИСЬ</span>
          <h1>{user.name || user.email}</h1>
          <p>{user.email} · {user.role === 'ADMIN' ? 'Администратор' : 'Пользователь'}</p>
        </div>
        <div className="account-actions">
          <button className="primary-action" onClick={() => onNavigate('projects')}>Мои проекты</button>
          {user.role === 'ADMIN' && (
            <button className="secondary-action" onClick={() => onNavigate('admin')}>Пользователи</button>
          )}
          <button className="danger-action" disabled={busy} onClick={logout}>Выйти</button>
        </div>
        {error && <p className="form-error">{error}</p>}
      </section>
    );
  }

  return (
    <section className="persistence-screen auth-screen narrow-screen">
      <div className="persistence-heading">
        <span className="eyebrow">СОХРАНЯЕМЫЕ ПРОЕКТЫ</span>
        <h1>{mode === 'login' ? 'Вход' : 'Регистрация'}</h1>
        <p>Гостевой расчёт остаётся доступен без учётной записи. Войдите, чтобы хранить проекты и версии расчётов.</p>
      </div>
      <div className="auth-tabs">
        <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Вход</button>
        <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Регистрация</button>
      </div>
      <form className="persistence-form" onSubmit={submit}>
        {mode === 'register' && (
          <label>Имя, необязательно<input value={form.name} maxLength="200" onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
        )}
        <label>Email<input type="email" required value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
        <label>Пароль<input type="password" required minLength="12" maxLength="128" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
        <small>Минимум 12 символов. Пароль хранится только как Argon2id-хеш.</small>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-action" disabled={busy} type="submit">{busy ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Создать аккаунт'}</button>
      </form>
    </section>
  );
}

export function ProjectsScreen({ onOpenProject, onOpenRun }) {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState('');
  const [expanded, setExpanded] = useState(null);
  const [runs, setRuns] = useState({});
  const [error, setError] = useState('');
  const csrf = readCsrfCookie();

  const load = async () => {
    try {
      const payload = await request('/api/projects');
      setProjects(payload.items);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    request('/api/projects')
      .then((payload) => setProjects(payload.items))
      .catch((err) => setError(err.message));
  }, []);

  const create = async (event) => {
    event.preventDefault();
    setError('');
    try {
      const project = await request('/api/projects', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrf },
        body: JSON.stringify({ name }),
      });
      setName('');
      setProjects((items) => [project, ...items]);
    } catch (err) {
      setError(err.message);
    }
  };

  const mutate = async (path, method, body = null) => {
    setError('');
    try {
      await request(path, {
        method,
        headers: { 'X-CSRF-Token': csrf },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const rename = (project) => {
    const nextName = window.prompt('Новое название проекта', project.name)?.trim();
    if (nextName && nextName !== project.name) {
      mutate(`/api/projects/${project.id}`, 'PATCH', { name: nextName });
    }
  };

  const toggleRuns = async (projectId) => {
    if (expanded === projectId) {
      setExpanded(null);
      return;
    }
    setExpanded(projectId);
    try {
      const payload = await request(`/api/projects/${projectId}/analysis-runs`);
      setRuns((items) => ({ ...items, [projectId]: payload.items }));
    } catch (err) {
      setError(err.message);
    }
  };

  const openRun = async (projectId, runId) => {
    try {
      const run = await request(`/api/projects/${projectId}/analysis-runs/${runId}`);
      onOpenRun(run, projects.find((project) => project.id === projectId));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="persistence-screen">
      <div className="persistence-heading">
        <span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span>
        <h1>Мои проекты</h1>
        <p>Каждый проект виден только владельцу. Новый проект сразу получает три сценарных слота.</p>
      </div>
      <form className="inline-create" onSubmit={create}>
        <input required maxLength="200" value={name} onChange={(event) => setName(event.target.value)} placeholder="Название нового проекта" />
        <button className="primary-action" type="submit">Создать</button>
      </form>
      {error && <p className="form-error">{error}</p>}
      <div className="project-list">
        {projects.length === 0 && <div className="empty-state">Пока нет сохранённых проектов.</div>}
        {projects.map((project) => (
          <article className="project-card" key={project.id}>
            <div>
              <h2>{project.name}</h2>
              <p>{project.description || 'Без описания'}</p>
              <div className="scenario-chips">{project.scenarios.map((scenario) => <span key={scenario.id}>{scenario.name}</span>)}</div>
            </div>
            <div className="card-actions">
              <button className="primary-action" onClick={() => onOpenProject(project)}>Открыть</button>
              <button className="secondary-action" onClick={() => toggleRuns(project.id)}>Расчёты</button>
              <button className="secondary-action" onClick={() => rename(project)}>Переименовать</button>
              <button className="secondary-action" onClick={() => mutate(`/api/projects/${project.id}/copy`, 'POST')}>Копировать</button>
              <button className="danger-action" onClick={() => window.confirm(`Удалить «${project.name}»?`) && mutate(`/api/projects/${project.id}`, 'DELETE')}>Удалить</button>
            </div>
            {expanded === project.id && (
              <div className="run-list">
                {(runs[project.id] || []).length === 0 && <p>Сохранённых расчётов нет.</p>}
                {(runs[project.id] || []).map((run) => (
                  <button key={run.id} onClick={() => openRun(project.id, run.id)}>
                    <strong>{run.status}</strong><span>{new Date(run.created_at).toLocaleString('ru-RU')}</span><small>{run.versions.catalog}</small>
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

export function AdminUsersScreen() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ email: '', password: '', name: '', role: 'USER' });
  const [error, setError] = useState('');
  const csrf = readCsrfCookie();

  const load = async () => {
    try {
      const payload = await request('/api/admin/users');
      setUsers(payload.items);
    } catch (err) {
      setError(err.message);
    }
  };
  useEffect(() => {
    request('/api/admin/users')
      .then((payload) => setUsers(payload.items))
      .catch((err) => setError(err.message));
  }, []);

  const create = async (event) => {
    event.preventDefault();
    try {
      await request('/api/admin/users', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrf },
        body: JSON.stringify(form),
      });
      setForm({ email: '', password: '', name: '', role: 'USER' });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const update = async (id, body) => {
    try {
      await request(`/api/admin/users/${id}`, {
        method: 'PATCH', headers: { 'X-CSRF-Token': csrf }, body: JSON.stringify(body),
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const resetPassword = async (id) => {
    const password = window.prompt('Новый пароль (минимум 12 символов)');
    if (!password) return;
    try {
      await request(`/api/admin/users/${id}/reset-password`, {
        method: 'POST', headers: { 'X-CSRF-Token': csrf }, body: JSON.stringify({ password }),
      });
      window.alert('Пароль сброшен, активные сессии пользователя закрыты.');
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (user) => {
    if (!window.confirm(`Удалить пользователя ${user.email} и все его проекты?`)) return;
    try {
      await request(`/api/admin/users/${user.id}`, {
        method: 'DELETE', headers: { 'X-CSRF-Token': csrf },
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="persistence-screen">
      <div className="persistence-heading">
        <span className="eyebrow">ADMIN</span><h1>Пользователи</h1>
        <p>Регистрация всегда создаёт USER. Только администратор может назначить роль ADMIN.</p>
      </div>
      <form className="admin-create-grid" onSubmit={create}>
        <input required type="email" placeholder="Email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        <input placeholder="Имя" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <input required minLength="12" type="password" placeholder="Пароль" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option>USER</option><option>ADMIN</option></select>
        <button className="primary-action" type="submit">Добавить</button>
      </form>
      {error && <p className="form-error">{error}</p>}
      <div className="user-table-wrap"><table className="user-table"><thead><tr><th>Пользователь</th><th>Роль</th><th>Статус</th><th>Действия</th></tr></thead><tbody>
        {users.map((user) => <tr key={user.id}><td><strong>{user.name || 'Без имени'}</strong><small>{user.email}</small></td><td><select value={user.role} onChange={(event) => update(user.id, { role: event.target.value })}><option>USER</option><option>ADMIN</option></select></td><td><button className={`status-control ${user.status.toLowerCase()}`} onClick={() => update(user.id, { status: user.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE' })}>{user.status}</button></td><td><button className="table-action" onClick={() => resetPassword(user.id)}>Сбросить пароль</button><button className="table-action danger" onClick={() => remove(user)}>Удалить</button></td></tr>)}
      </tbody></table></div>
    </section>
  );
}
