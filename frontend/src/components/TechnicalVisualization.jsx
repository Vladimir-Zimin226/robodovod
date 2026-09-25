import { useState } from 'react';
import { buildPartialEconomicsRunRequest } from '../economicsInputV2';
import { buildTechnicalSimulationRequest } from '../economicsSimulationRequest';
import { economicsFieldLabel } from '../economicsFieldLabels';
import { readCsrfCookie } from '../persistenceApi';
import Simulation2DReport from './Simulation2DReport';
import { modelTimezone, timezoneChoices } from '../simulationDefaults';

const API = import.meta.env.VITE_API_URL || '';

export default function TechnicalVisualization({ run, capacityRequest, project, capacityRunId }) {
  const [technicalRun, setTechnicalRun] = useState(null);
  const [startTime, setStartTime] = useState('09:00');
  const [timezone, setTimezone] = useState(() => modelTimezone(project));
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
        throw new Error('Выберите местный часовой пояс для нового сценария.');
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
      if (!response.ok) throw new Error(payload.issues?.[0]?.next_step || payload.detail || 'Не удалось сохранить технический расчёт.');
      setTechnicalRun(payload);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };

  return <section className="technical-visualization mx-auto my-6 max-w-6xl space-y-3" aria-label="Симуляция процесса">
    <div className="technical-visualization-intro rounded-xl border p-4">
      <h2 className="font-semibold">Симуляция процесса · 2D и 3D</h2>
      <p className="text-sm">Показатели берутся из сохранённой симуляции процесса. Геометрия без плана объекта условная; это не телеметрия. Денежный эффект рассчитывается отдельно.</p>
      {request ? <p className="text-sm text-green-800">Схема работы доступна. {current?.result_snapshot?.branches?.purchase?.status !== 'CALCULATED' ? 'Денежный эффект не рассчитан.' : 'Экономические ветки показаны отдельно.'}</p>
        : <p className="text-sm text-amber-800">Схема работы пока недоступна. {reasons.length ? `Нужно уточнить: ${reasons.map(economicsFieldLabel).join(', ')}.` : 'Создайте связанный технический расчёт.'}</p>}
      {!request && capacityRequest && project && capacityRunId && <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={create}>
        <p className="w-full text-sm">Модельное начало нового сценария: понедельник, {startTime} местного времени. Время нажатия «Старт» на него не влияет.</p>
        <label className="text-sm">Часовой пояс<select className="block rounded border p-2" value={timezone} onChange={(event) => setTimezone(event.target.value)} required><option value="">Выберите пояс</option>{timezoneChoices(timezone).map((zone) => <option key={zone} value={zone}>{zone.replaceAll('_', ' ')}</option>)}</select></label>
        <details className="text-sm"><summary>Детальная настройка времени</summary><label>Начало работы · местное время<input className="block rounded border p-2" type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} required /></label></details>
        <button type="submit" className="primary-action" disabled={busy || !timezone}>{busy ? 'Сохраняем…' : 'Показать симуляцию'}</button>
        <p className="w-full text-xs">Исходный расчёт парка остаётся неизменным; новый расчёт будет связан с ним и доступен в проекте.</p>
      </form>}
      {!request && !capacityRequest && <p className="text-xs">Для сохранённого частичного расчёта откройте редактор ниже и сохраните новый расчёт с предложенным местным временем. Если не хватает маршрута или графика, вернитесь к вводу процесса.</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
    </div>
    {request && <Simulation2DReport key={current.id} request={request} analysisRunId={current.id} />}
  </section>;
}
