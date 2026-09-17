import { useRef, useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';

const API = import.meta.env.VITE_API_URL || '';
const PROFILE_CODES = { retail: 'warehouse', airport: 'airport', clinic: 'medical_facility' };

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
      if (mode === 'apply') form.append('scenario_id', scenario.id);
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
        throw new Error(typeof detail === 'string' ? detail : 'Файл не прошёл проверку');
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
        {preview.report.errors?.slice(0, 8).map((item, index) => <small key={`${item.code}-${item.parameter_code || index}`}>{item.parameter_code ? `${item.parameter_code}: ` : ''}{item.message}</small>)}
      </div>}
      {state === 'applied' && <div className="file-applied">Файл сохранён, значения применены к проекту.</div>}
      {error && <div className="file-error">{error}</div>}
    </section>
  );
}
