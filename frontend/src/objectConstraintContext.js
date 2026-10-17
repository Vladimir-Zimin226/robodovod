export const OBJECT_CONSTRAINT_FIELDS = [
  ['max_payload_kg', 'Требуемая грузоподъёмность за рейс, кг'], ['min_aisle_width_m', 'Доступная ширина прохода, м'],
  ['required_lift_height_m', 'Требуемая высота подъёма, м'], ['ceiling_height_m', 'Высота потолка, м'],
  ['floor_flatness_mm_2m', 'Неровность пола на 2 м, мм'], ['max_slope_percent', 'Уклон маршрута, %'],
  ['available_charging_power_kw', 'Доступная мощность зарядки, кВт'],
  ['temperature_min_c', 'Минимальная температура на маршруте, °C'],
  ['temperature_max_c', 'Максимальная температура на маршруте, °C'],
];

export const objectConstraintLabel = key => Object.fromEntries(OBJECT_CONSTRAINT_FIELDS)[key]
  || {outdoor_required:'Работа на улице', floor_covering:'Покрытие пола'}[key] || key;

export function buildObjectConstraintContext(zone, process, facility = null) {
  const present = data => Object.fromEntries(Object.entries(data?.values || {}).filter(([, value]) => value !== '' && value != null && value !== false));
  const facilityValues = present(facility?.objectConstraints);
  const zoneValues = present(zone?.objectConstraints);
  if (Object.keys(facilityValues).length && !facility.objectConstraints.confirmed) throw new Error('Подтвердите общие условия объекта.');
  if (Object.keys(zoneValues).length && !zone.objectConstraints.confirmed) throw new Error('Подтвердите ограничения зоны.');
  const values = { ...facilityValues, ...zoneValues };
  if (!Object.keys(values).length && process.item_mass?.status !== 'KNOWN') return null;
  const context = { object_kind: process.object_kind, ...values, requirement_sources: {} };
  const units = process.explicit_batch?.status === 'KNOWN' ? Number(process.explicit_batch.normalized_value) : 1;
  if (process.item_mass?.status === 'KNOWN' && context.max_payload_kg == null)
    context.max_payload_kg = String(Number(process.item_mass.normalized_value) * units);
  if (process.item_mass?.status === 'KNOWN' && context.max_payload_kg != null) {
    if (Number(context.max_payload_kg) < Number(process.item_mass.normalized_value) * units) {
      throw new Error('Требуемая грузоподъёмность ниже массы перевозимой партии.');
    }
  }
  for (const field of Object.keys(context).filter(key => !['object_kind', 'requirement_sources'].includes(key))) {
    const sourceRef = Object.hasOwn(zoneValues, field) ? `object.${zone.zoneId}.${field}.${process.input_revision}`
      : Object.hasOwn(facilityValues, field) ? `object.facility.${field}.${process.input_revision}`
        : process.item_mass.provenance_ref || `process.${process.process_id || 'unknown'}.item_mass.${process.input_revision || 'draft'}`;
    context.requirement_sources[field] = { kind: 'USER', user_confirmed: true, source_ref: sourceRef };
  }
  return context;
}
