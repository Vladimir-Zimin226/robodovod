// Browser-side request assembly only. All formulae and evidence gates remain server-owned.
// Authored profiles use stable organizer_id; C11 must still receive the catalog's model_id.
export const DEMO_MODELS = Object.freeze({
  'ecd7d582-b342-449a-b43b-66288d159a32': 'MULE · демонстрационный профиль',
  '5760e938-9a43-45a7-b8e8-f4f2e6383930': 'Ronavi H1500 · демонстрационный профиль',
  '446c5207-a099-45e0-b615-afd60de08589': 'MARK 2 SE · демонстрационный профиль',
});

// These are author-authored demo notes, not manufacturer passports or C05 evidence.
// Keep the visible caveats alongside the model picker so they cannot be missed.
export const DEMO_PROFILES = Object.freeze({
  'ecd7d582-b342-449a-b43b-66288d159a32': Object.freeze({
    sourceLabel: 'СМ Роботикс · MULE', sourceUrl: 'https://sm-robotics.ru/',
    published: 'Производитель: грузоподъёмность до 1 500 кг, скорость до 1,3 м/с.',
    assumptions: 'Типовой склад организаторов: 800 кг/паллету, 2 000 паллет/сутки, 2×11 ч; плечо 120 м и предзаполненный обмен 90 с — отдельные редактируемые допущения сценария.',
    unknown: 'Не проверены техпаспорт комплектации, проход, пол, доступность в смене, фактический обмен и условия поставки.',
  }),
  '5760e938-9a43-45a7-b8e8-f4f2e6383930': Object.freeze({
    sourceLabel: 'Ронави Роботикс · H1500', sourceUrl: 'https://ronavi-robotics.ru/catalogue/h1500',
    conflictUrl: 'https://ronavi-robotics.ru/media/kak-rabotaet-robotizirovannaya-zona-na-sklade-vostok-servis',
    published: 'Производитель: до 1 500 кг и минимальный проезд 750 мм; разные страницы указывают 1,3 и 1,5 м/с.',
    assumptions: 'Типовой склад организаторов и плечо 120 м; подходящий модуль для паллет, цикл обмена и скорость выбранной комплектации требуют подтверждения.',
    unknown: 'Не проверены техпаспорт и оснастка, эксплуатационная доступность, условия пола и цена комплектации.',
  }),
  '446c5207-a099-45e0-b615-afd60de08589': Object.freeze({
    sourceLabel: 'Р2Б · MARK 2 SE', sourceUrl: 'https://r2b.company/mark2se',
    published: 'Производитель: примерно 600–700 м²/ч в реальных условиях; 600 м²/ч — консервативная оценка для демо.',
    assumptions: 'Активная зона 10 000 м² — типовое значение организаторов; одна уборка в сутки — допущение сценария.',
    unknown: 'Не проверены паспорт комплектации, покрытие и ровность, доступность, шум, сервис и расходники.',
  }),
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
    item.calculation_profile === profile && item.maturity_status !== 'RND');
}

export function brainCandidates(items, scope) {
  const profile = scope === 'CLEANING_AREA' ? 'CLEANING_AREA_V1' :
    ['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(scope) ? 'TRANSPORT_CYCLE_V1' : null;
  if (!profile) return [];
  const seen = new Set();
  return items.filter((item) => {
    if (!item.calculation_ready || item.maturity_status === 'RND' || item.calculation_profile !== profile || seen.has(item.position_id)) return false;
    seen.add(item.position_id);
    return true;
  });
}

export function buildDemoCapacityRequest({ normalized, projectId, processId, position, exchangeSeconds, cleaningFrequency = '1', acknowledged, zone, brainProfileVersion = null }) {
  if (!acknowledged) throw new Error('Подтвердите демонстрационные допущения.');
  if (!projectId) throw new Error('Откройте проект для сохранения расчёта.');
  const process = normalized?.response?.normalized_processes?.find((item) => item.process_id === processId);
  if (!process?.active || process.input_revision !== normalized.response.input_revision) {
    throw new Error('Нормализуйте активный процесс заново.');
  }
  if (!position || !position.position_id || !position.calculation_ready || position.maturity_status === 'RND' || position.selection?.status === 'EXCLUDED') {
    throw new Error('Выберите совместимую расчётную модель из активного каталога.');
  }
  const expectedProfile = process.scope === 'CLEANING_AREA' ? 'CLEANING_AREA_V1' :
    ['TRANSPORT_CYCLE', 'DELIVERY_CYCLE'].includes(process.scope) ? 'TRANSPORT_CYCLE_V1' : null;
  if (!expectedProfile || position.calculation_profile !== expectedProfile) {
    throw new Error('Модель не соответствует физическому профилю процесса.');
  }
  const provenance = [{
    provenance_id: 'prov.demo.confirmation', kind: 'ASSUMPTION',
    assumption_id: brainProfileVersion ? 'brain-preliminary-applicability' : 'organizer-demo-object',
    assumption_version: brainProfileVersion ? `profile-v${brainProfileVersion}` : 'v1',
    rationale: brainProfileVersion ? 'Предварительный сценарий пользователя; пригодность модели, скорость и обмен требуют проверки на объекте' : 'Параметры типового объекта требуют проверки на реальном объекте',
    permitted_scope: process.scope, confirmation_state: 'USER_CONFIRMED',
  }];
  const requestProcess = { ...process };
  if (!zone || !process.process_id.startsWith(`${zone.zoneId}.`) || !zone.label?.trim()) {
    throw new Error('Выберите зону для процесса и укажите её название.');
  }
  const request = {
    schema_version: 'capacity-analysis-request-v3',
    project_id: projectId, input_revision: process.input_revision,
    process: requestProcess,
    zone_context: { schema_version: 'capacity-zone-context-v1', zone_id: zone.zoneId,
      label: zone.label.trim(), constraints_note: String(zone.constraints || '').trim(), constraints_status: 'UNVERIFIED' },
    role_pool: normalized.response.role_pool ? {
      ...normalized.response.role_pool,
      roles: normalized.response.role_pool.roles.filter((role) => (process.role_refs || []).includes(role.role_id))
        .map((role) => ({ ...role, process_ids: [process.process_id] })),
    } : null,
    model_id: position.model_id, position_id: position.position_id,
    acquisition: 'PURCHASE', uncertainty: 'BASE',
    execution_mode: 'PRELIMINARY_DEMO', demo_assumptions_confirmed: true,
    provenance,
  };
  const rawAreas = normalized.response.raw_extensions?.facility_areas;
  if (rawAreas?.total_area || rawAreas?.active_area) {
    const area = (raw) => raw ? { value: raw.value, unit: 'm2',
      source: raw.provenance.source, confirmed: raw.provenance.user_confirmed === true } : null;
    request.facility_context = { schema_version: 'facility-context-v1',
      total_area: area(rawAreas.total_area), active_area: area(rawAreas.active_area) };
  }
  if (process.scope === 'CLEANING_AREA') {
    // One cleaning pass per day is an explicit demo assumption, never inferred by C11.
    if (!positive(cleaningFrequency)) throw new Error('Укажите число уборок площади в сутки.');
    request.cleaning_area = quantity('cleaning_area', process.demand?.normalized_value, 'm2', 'AREA', 'prov.demo.confirmation');
    request.cleaning_frequency = quantity('cleaning_frequency', cleaningFrequency, '1/day', 'RATE', 'prov.demo.confirmation');
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
