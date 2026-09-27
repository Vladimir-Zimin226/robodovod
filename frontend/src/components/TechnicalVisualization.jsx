import { useEffect, useState } from 'react';
import { automaticTechnicalRun } from '../automaticTechnicalRun';
import { buildTechnicalSimulationRequest } from '../economicsSimulationRequest';
import { economicsFieldLabel } from '../economicsFieldLabels';
import Simulation2DReport from './Simulation2DReport';
import { modelTimezone, timezoneChoices } from '../simulationDefaults';


export default function TechnicalVisualization({ run, capacityRequest, project, capacityRunId, autoStart = false, onReady }) {
  const [technicalRun, setTechnicalRun] = useState(null);
  const [startTime, setStartTime] = useState('09:00');
  const [timezone, setTimezone] = useState(() => modelTimezone(project));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const current = technicalRun || run;
  const request = buildTechnicalSimulationRequest(current);
  const reasons = current?.scenario_spec_snapshot?.required_fields || current?.result_snapshot?.visualization?.required_fields || [];

  const create = async (event) => {
    event?.preventDefault();
    setError(''); setBusy(true);
    try {
      const payload = await automaticTechnicalRun({ project, capacityRequest, capacityRunId, startTime, timezone });
      setTechnicalRun(payload);
      onReady?.(payload);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    if (!autoStart || request || !capacityRequest || !project?.id || !capacityRunId) return undefined;
    let active = true;
    automaticTechnicalRun({ project, capacityRequest, capacityRunId, startTime, timezone })
      .then((payload) => { if (active) { setTechnicalRun(payload); onReady?.(payload); } })
      .catch((failure) => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [autoStart, request, capacityRequest, project, capacityRunId, startTime, timezone, onReady]);

  return <section className="technical-visualization mx-auto my-6 max-w-6xl space-y-3" aria-label="Симуляция процесса">
    <div className="technical-visualization-intro rounded-xl border p-4">
      <h2 className="font-semibold">Симуляция процесса · 2D и 3D</h2>
      <p className="text-sm">Показатели берутся из сохранённой симуляции процесса. Геометрия без плана объекта условная; это не телеметрия. Денежный эффект рассчитывается отдельно.</p>
      {request ? <p className="text-sm text-green-800">Схема работы доступна. {current?.result_snapshot?.branches?.purchase?.status !== 'CALCULATED' ? 'Денежный эффект не рассчитан.' : 'Экономические ветки показаны отдельно.'}</p>
        : <p className="text-sm text-amber-800">Схема работы пока недоступна. {reasons.length ? `Нужно уточнить: ${reasons.map(economicsFieldLabel).join(', ')}.` : autoStart && !error ? 'Подготавливаем и запускаем симуляцию…' : 'Уточните входы и повторите запуск.'}</p>}
      {!request && (!autoStart || error) && capacityRequest && project && capacityRunId && <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={create}>
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
