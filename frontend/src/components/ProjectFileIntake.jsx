import { useRef, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const PROFILE_CODES = { retail: 'warehouse', airport: 'airport', clinic: 'medical_facility' };
const FILE_ERRORS = {
  FILE_TOO_LARGE: 'Файл больше 5 МБ. Уменьшите книгу и повторите загрузку.',
  XLSX_MACROS_FORBIDDEN: 'Макросы не принимаются. Сохраните книгу как обычный XLSX без макросов.',
  XLSX_ARCHIVE_LIMIT_EXCEEDED: 'Книга слишком велика после распаковки. Удалите лишние данные и повторите загрузку.',
  XLSX_DIMENSIONS_LIMIT_EXCEEDED: 'Превышен размер листа. Используйте исходный шаблон, не более 3000 строк на лист.',
  CSV_HEADER_INVALID: 'Заголовки CSV не совпадают с шаблоном. Скачайте совместимый CSV и сохраните его колонки.',
  XLSX_INVALID: 'Книга повреждена или не является XLSX. Откройте её в табличном редакторе и сохраните снова.',
};

export default function ProjectFileIntake({ objectType, project, scenario, onApplied }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState('');
  const [error, setError] = useState('');
  const profileCode = PROFILE_CODES[objectType];

  if (!project || !scenario || !profileCode) return null;

  const request = async (mode) => {
    if (!file) return;
    setState(mode);
    setError('');
    try {
      const form = new FormData();
      form.append('profile_code', profileCode);
      if (mode === 'apply') {
        form.append('scenario_id', scenario.id);
        form.append('expected_import_id', preview?.previous_import_id || '__none__');
        if (preview?.project_profile_sha256) form.append('expected_profile_sha256', preview.project_profile_sha256);
        if (preview?.sha256) form.append('expected_file_sha256', preview.sha256);
      }
      form.append('file', file);
      const response = await fetch(`${API}/api/projects/${project.id}/files/${mode}`, {
        method: 'POST', credentials: 'include',
        headers: mode === 'apply' ? { 'X-CSRF-Token': readCsrfCookie() } : {},
        body: form,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail;
        const report = typeof detail === 'object' ? detail.report : null;
        if (report) setPreview({ valid: false, report });
        throw new Error(typeof detail === 'string' ? FILE_ERRORS[detail] || detail : 'Файл не прошёл проверку');
      }
      if (mode === 'preview') {
        setPreview(payload);
      } else {
        setPreview({ valid: true, report: payload.import.validation_report });
        onApplied(payload.import.normalized_input, payload.import.provenance, payload.import);
        setState('applied');
        return;
      }
    } catch (requestError) {
      setError(requestError.message || 'Не удалось обработать файл');
    }
    setState('');
  };

  const choose = (event) => {
    setFile(event.target.files?.[0] || null);
    setPreview(null);
    setError('');
    setState('');
  };

  return (
    <section className="project-file-intake">
      <div><strong>Данные проекта из XLSX/CSV</strong><p>Сначала проверьте файл. Проект изменится только после нажатия «Применить».</p></div>
      <input ref={inputRef} hidden type="file" accept=".xlsx,.csv" onChange={choose} />
      <div className="project-file-actions">
        <button className="secondary-action" type="button" onClick={() => inputRef.current?.click()}>{file ? file.name : 'Выбрать файл'}</button>
        <button className="secondary-action" type="button" disabled={!file || state === 'preview'} onClick={() => request('preview')}>{state === 'preview' ? 'Проверяем…' : 'Проверить'}</button>
        <a className="secondary-action" href={`${API}/api/project-file-templates/${profileCode}.csv`}>CSV-шаблон</a>
        {preview?.valid && state !== 'applied' && <button className="primary-action" type="button" disabled={state === 'apply'} onClick={() => request('apply')}>{state === 'apply' ? 'Применяем…' : 'Применить к базовому сценарию'}</button>}
      </div>
      {preview && <div className={preview.valid ? 'file-report valid' : 'file-report invalid'}>
        <b>{preview.valid ? 'Файл прошёл проверку' : 'Найдены ошибки'}</b>
        <span>Принято параметров: {preview.report.accepted_count}/{preview.report.parameter_count}; ошибок: {preview.report.error_count}</span>
        {preview.report.errors?.map((item, index) => <small key={`${item.code}-${index}`}>{item.sheet} {item.row ? `строка ${item.row}` : ''} {item.parameter_code}: {item.message}. {item.next_step}</small>)}
        {preview.report.warnings?.map((item, index) => <small key={index}>{item.message}</small>)}
        <p>Неизвестно: {preview.report.unknown_fields?.length || 0}. Нужны для выбранного расчёта: {preview.report.required_inputs?.join(', ') || 'проверка и подтверждение пользователя'}.</p>
        <details><summary>Источники и предложения</summary>{preview.report.sources?.map((item) => <p key={item.field}>{item.field}: {item.value} {item.unit} · {item.status} · {item.source}</p>)}</details>
        <details><summary>Изменения к проекту: {preview.diff?.length || 0}</summary>{preview.diff?.map((item) => <p key={item.field}>{item.field}: {item.before?.value ?? 'неизвестно'} → {item.after?.value ?? 'неизвестно'} ({item.after?.status || 'предложение'})</p>)}</details>
      </div>}
      {state === 'applied' && <div className="file-applied">Файл сохранён, значения применены к проекту.</div>}
      {error && <div className="file-error">{error}</div>}
    </section>
  );
}
