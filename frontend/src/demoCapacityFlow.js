// Browser-side request assembly only. All formulae and evidence gates remain server-owned.
export const DEMO_MODELS = Object.freeze({
  'ecd7d582-b342-449a-b43b-66288d159a32': 'MULE · демонстрационный профиль',
  '5760e938-9a43-45a7-b8e8-f4f2e6383930': 'Ronavi H1500 · демонстрационный профиль',
  '446c5207-a099-45e0-b615-afd60de08589': 'MARK 2 SE · демонстрационный профиль',
});

const quantity = (name, value, unit, kind, provenanceRef) => ({
  status: 'KNOWN', name, raw_value: String(value), raw_unit: unit,
  normalized_value: String(value), unit, quantity_kind: kind,
  numeric_encoding: 'DECIMAL_STRING', provenance_ref: provenanceRef,
});

const positive = (value) => /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(String(value)) && Number(value) > 0;

export function demoCandidates(items, scope) {
  const profile = scope === 'CLEANING_AREA' ? 'CLEANING_AREA_V1' :
    ['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(scope) ? 'TRANSPORT_CYCLE_V1' : null;
  if (!profile) return [];
  return items.filter((item) => item.calculation_ready &&
    item.calculation_profile === profile && DEMO_MODELS[item.model_id]);
}

export function buildDemoCapacityRequest({ normalized, projectId, processId, position, exchangeSeconds, acknowledged }) {
  if (!acknowledged) throw new Error('Подтвердите демонстрационные допущения.');
  if (!projectId) throw new Error('Откройте проект для сохранения расчёта.');
  const process = normalized?.response?.normalized_processes?.find((item) => item.process_id === processId);
  if (!process?.active || process.input_revision !== normalized.response.input_revision) {
    throw new Error('Нормализуйте активный процесс заново.');
  }
  if (!position || !DEMO_MODELS[position.model_id] || !position.calculation_ready) {
    throw new Error('Выберите расчётную модель из демо-профилей.');
  }
  const expectedProfile = process.scope === 'CLEANING_AREA' ? 'CLEANING_AREA_V1' :
    ['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) ? 'TRANSPORT_CYCLE_V1' : null;
  if (!expectedProfile || position.calculation_profile !== expectedProfile) {
    throw new Error('Модель не соответствует физическому профилю процесса.');
  }
  const provenance = [{
    provenance_id: 'prov.demo.confirmation', kind: 'ASSUMPTION',
    assumption_id: 'organizer-demo-object', assumption_version: 'v1',
    rationale: 'Параметры типового объекта требуют проверки на реальном объекте',
    permitted_scope: process.scope, confirmation_state: 'USER_CONFIRMED',
  }];
  const requestProcess = { ...process };
  const request = {
    project_id: projectId, input_revision: process.input_revision,
    process: requestProcess, role_pool: normalized.response.role_pool,
    model_id: position.model_id, position_id: position.position_id,
    acquisition: 'PURCHASE', uncertainty: 'BASE',
    execution_mode: 'PRELIMINARY_DEMO', demo_assumptions_confirmed: true,
    provenance,
  };
  if (process.scope === 'CLEANING_AREA') {
    // One cleaning pass per day is an explicit demo assumption, never inferred by C11.
    request.cleaning_area = quantity('cleaning_area', process.demand?.normalized_value, 'm2', 'AREA', 'prov.demo.confirmation');
    request.cleaning_frequency = quantity('cleaning_frequency', '1', '1/day', 'RATE', 'prov.demo.confirmation');
  } else {
    if (!positive(exchangeSeconds)) throw new Error('Укажите время погрузки и выгрузки за рейс, сек.');
    requestProcess.exchange = {
      mode: 'TOTAL',
      total_time: quantity('exchange_total_time', exchangeSeconds, 's', 'TIME', 'prov.demo.confirmation'),
    };
    if (!process.route_distance || process.route_distance.status !== 'KNOWN') {
      throw new Error('Укажите одностороннее плечо маршрута.');
    }
    if (!process.explicit_batch || process.explicit_batch.status !== 'KNOWN') {
      throw new Error('Укажите единиц груза за рейс.');
    }
  }
  return request;
}
