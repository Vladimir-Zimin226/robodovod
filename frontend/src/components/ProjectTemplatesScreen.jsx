import { useState } from 'react';
import ProjectFileIntake from './ProjectFileIntake';

const API = import.meta.env.VITE_API_URL || '';
const PROFILES = { retail: 'warehouse', airport: 'airport', clinic: 'medical_facility' };
export default function ProjectTemplatesScreen({ user, project, projects, onChooseProject, onApplied, onNavigate }) {
  const [objectType, setObjectType] = useState('retail');
  const [message, setMessage] = useState('');
  const url = (variant, extension) => `${API}/api/project-workbooks/${PROFILES[objectType]}/${variant}.${extension}`;
  const copy = async () => {
    try {
      const response = await fetch(url('interview', 'txt'));
      if (!response.ok) throw new Error();
      await navigator.clipboard.writeText(await response.text());
      setMessage('Промпт скопирован.');
    } catch { setMessage('Скачайте TXT и скопируйте текст из файла.'); }
  };
  return <main className="project-templates-screen p-6" aria-label="Шаблоны и загрузка данных">
    <h1 className="text-2xl font-semibold">Шаблоны и загрузка данных</h1>
    <p className="my-4">Скачайте пустую книгу и промпт. Передайте их ChatGPT, Claude или другой LLM и ответьте на вопросы интервью. Загрузите заполненный файл, проверьте предложения и отдельно подтвердите входы перед расчётом.</p>
    <label>Объект <select value={objectType} onChange={(event) => setObjectType(event.target.value)}>
      <option value="retail">Склад</option><option value="airport">Аэропорт</option><option value="clinic">Клиника</option>
    </select></label>
    <div className="project-file-actions my-4">
      <a className="secondary-action" href={url('blank', 'xlsx')}>Пустой XLSX</a>
      <a className="secondary-action" href={url('demo', 'xlsx')}>Demo XLSX</a>
      <a className="secondary-action" href={url('blank', 'csv')}>Совместимый CSV</a>
      <a className="secondary-action" href={url('demo', 'csv')}>Demo CSV</a>
      <a className="secondary-action" href={url('interview', 'txt')}>Промпт TXT</a>
      <button type="button" className="secondary-action" onClick={copy}>Копировать промпт</button>
    </div>
    <p>В demo числа организаторов помечены ASSUMPTION. UNKNOWN означает отсутствие данных. Паспорт сохраняется полностью; обязательны только входы выбранной формулы. Расчётные модели аэропорта и клиники требуют отдельной проверки доступности каталога.</p>
    {message && <p role="status">{message}</p>}
    {!user ? <button className="primary-action my-4" onClick={() => onNavigate('account')}>Войти для сохранения импорта</button>
      : <><label>Проект <select value={project?.id || ''} onChange={(event) => {
        const selected = projects.find((item) => item.id === event.target.value);
        if (selected) onChooseProject(selected);
      }}><option value="">Выберите проект</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        {!project && <button className="secondary-action" onClick={() => onNavigate('projects')}>Создать проект</button>}
        <ProjectFileIntake key={`${project?.id}:${objectType}`} objectType={objectType} project={project} scenario={project?.scenarios?.find((item) => item.slot === 'BASE')} onApplied={onApplied} />
        {project?.profile?.file_intake_v2 && <div className="project-file-actions"><button className="primary-action" onClick={() => onNavigate('intake', project.profile.file_intake_v2.object_type)}>Проверить и подтвердить в форме</button>
          <button className="secondary-action" onClick={() => onNavigate('model')}>Открыть в Brain</button></div>}
      </>}
  </main>;
}
