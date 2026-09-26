import { buildEconomicsSimulationRequest, buildTechnicalSimulationRequest } from './economicsSimulationRequest.js';

const quantity = (q) => q ? `${q.value} ${q.unit}` : 'не задано';

export function physicalInputs(spec) {
  return [
    `Процесс: ${spec.profile.process_code} · ${spec.profile.process_id}`,
    ...spec.tasks.map((task) => `Спрос: ${quantity(task.demand)} · за рейс: ${quantity(task.batch.units_per_cycle)} · операции: ${task.exchange.mode} ${quantity(task.exchange.total_time)}`),
    ...spec.routes.map((route) => `Плечо: ${quantity(route.one_way_distance)}`),
    ...spec.fleet.map((fleet) => `Модель: ${fleet.model_id} · позиция: ${fleet.position_id} · парк: ${fleet.selected_fleet} · мощность: ${quantity(fleet.nominal_capacity)} / эффективная: ${quantity(fleet.effective_capacity)}`),
    ...spec.operating_windows.map((window) => `График: ${quantity(window.duration)} · начало: ${quantity(window.start_time)} · ${window.timezone}`),
  ];
}

export function physicalRunOption(run) {
  const request = buildTechnicalSimulationRequest(run)
    || buildEconomicsSimulationRequest(run.result_snapshot, run.scenario_spec_snapshot);
  if (!request) return null;
  const spec = request.scenario_spec;
  return { id: run.id, request, label: `${spec.tasks.map((task) => quantity(task.demand)).join(', ')} · ${spec.routes.map((route) => quantity(route.one_way_distance)).join(', ')} · парк ${spec.fleet.map((fleet) => fleet.selected_fleet).join(', ')} · ${run.id.slice(0, 8)}` };
}
