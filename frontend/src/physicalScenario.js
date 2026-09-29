import { buildEconomicsSimulationRequest, buildTechnicalSimulationRequest } from './economicsSimulationRequest.js';
import { PROCESS_DEFINITIONS } from './processRoleIntakeV2.js';

const quantity = (q) => q ? `${q.value} ${q.unit}` : 'не задано';

export function physicalInputs(spec) {
  const process = PROCESS_DEFINITIONS.find((item) => item.code === spec.profile.process_code)?.label || 'Выбранный процесс';
  const exchange = { TOTAL: 'общее время обмена', SPLIT: 'раздельная загрузка и выгрузка' };
  return [
    `Процесс: ${process}`,
    ...spec.tasks.map((task) => `Спрос: ${quantity(task.demand)} · за рейс: ${quantity(task.batch.units_per_cycle)} · ${exchange[task.exchange.mode] || 'время обмена'}: ${quantity(task.exchange.total_time)}`),
    ...spec.routes.map((route) => `Плечо: ${quantity(route.one_way_distance)}`),
    ...spec.fleet.map((fleet) => `Выбранная модель · парк: ${fleet.selected_fleet} · мощность: ${quantity(fleet.nominal_capacity)} / эффективная: ${quantity(fleet.effective_capacity)}`),
    ...spec.operating_windows.map((window) => `График: ${quantity(window.duration)} · начало: ${quantity(window.start_time)} · ${window.timezone}`),
  ];
}

export function physicalRunOption(run) {
  const request = buildTechnicalSimulationRequest(run)
    || buildEconomicsSimulationRequest(run.result_snapshot, run.scenario_spec_snapshot);
  if (!request) return null;
  const spec = request.scenario_spec;
  return { id: run.id, request, label: `${spec.tasks.map((task) => quantity(task.demand)).join(', ')} · ${spec.routes.map((route) => quantity(route.one_way_distance)).join(', ')} · парк ${spec.fleet.map((fleet) => fleet.selected_fleet).join(', ')}${run.created_at ? ` · ${new Date(run.created_at).toLocaleString('ru-RU')}` : ''}` };
}
