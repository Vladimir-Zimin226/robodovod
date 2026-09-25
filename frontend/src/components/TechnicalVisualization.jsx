import { useState } from 'react';
import { buildPartialEconomicsRunRequest } from '../economicsInputV2';
import { buildTechnicalSimulationRequest } from '../economicsSimulationRequest';
import { economicsFieldLabel } from '../economicsFieldLabels';
import { readCsrfCookie } from '../persistenceApi';
import Simulation2DReport from './Simulation2DReport';

const API = import.meta.env.VITE_API_URL || '';

export default function TechnicalVisualization({ run, capacityRequest, project, capacityRunId }) {
  const [technicalRun, setTechnicalRun] = useState(null);
  const [startTime, setStartTime] = useState('');
  const [timezone, setTimezone] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const current = technicalRun || run;
  const request = buildTechnicalSimulationRequest(current);
  const reasons = current?.scenario_spec_snapshot?.required_fields || current?.result_snapshot?.visualization?.required_fields || [];

  const create = async (event) => {
    event.preventDefault();
    setError(''); setBusy(true);
    try {
      const [hours, minutes] = startTime.split(':').map(Number);
      if (!startTime || !Number.isInteger(hours) || !Number.isInteger(minutes) || hours > 23 || minutes > 59 || !timezone.trim()) {
        throw new Error('Укажите начало работы и часовой пояс IANA.');
      }
      const body = buildPartialEconomicsRunRequest({
        values: { capacityRunId, startSeconds: String(hours * 3600 + minutes * 60), timezone: timezone.trim() },
        capacityRequest, project, scenario: project?.scenarios?.find((item) => item.slot === 'BASE'),
      });
      const response = await fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.issues?.[0]?.next_step || payload.detail || 'Не удалось сохранить технический run.');
      setTechnicalRun(payload);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };

  return <section className="technical-visualization mx-auto my-6 max-w-6xl space-y-3" aria-label="Техническая визуализация C23">
    <div className="technical-visualization-intro rounded-xl border p-4">
      <h2 className="font-semibold">2D/C23 · схема работы</h2>
      <p className="text-sm">KPI получаются из сохранённого отчёта C23. Геометрия без плана объекта условная; это не телеметрия. Денежный эффект рассчитывается отдельно.</p>
      {request ? <p className="text-sm text-green-800">Схема работы доступна. {current?.result_snapshot?.branches?.purchase?.status !== 'CALCULATED' ? 'Денежный эффект не рассчитан.' : 'Экономические ветки показаны отдельно.'}</p>
        : <p className="text-sm text-amber-800">Схема работы пока недоступна. {reasons.length ? `Нужно уточнить: ${reasons.map(economicsFieldLabel).join(', ')}.` : 'Укажите календарь и создайте новый связанный run.'}</p>}
      {!request && capacityRequest && project && capacityRunId && <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={create}>
        <label className="text-sm">Начало работы · местное время<input className="block rounded border p-2" type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} required /></label>
        <label className="text-sm">Часовой пояс IANA<input className="block rounded border p-2" value={timezone} onChange={(event) => setTimezone(event.target.value)} placeholder="Europe/Moscow" required /></label>
        <button type="submit" className="primary-action" disabled={busy}>{busy ? 'Сохраняем…' : 'Создать технический run для 2D'}</button>
        <p className="w-full text-xs">Исходный C11 остаётся неизменным; новый run будет связан с ним и доступен в проекте.</p>
      </form>}
      {!request && !capacityRequest && <p className="text-xs">Для сохранённого частичного run откройте редактор ниже, заполните начало работы и часовой пояс и создайте новый run. Если не хватает маршрута или графика C11, вернитесь к вводу процесса.</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
    </div>
    {request && <Simulation2DReport key={current.id} request={request} analysisRunId={current.id} />}
  </section>;
}
