export const OBJECT_CONSTRAINT_FIELDS = [
  ['max_payload_kg', 'Требуемая грузоподъёмность за рейс, кг'], ['min_aisle_width_m', 'Доступная ширина прохода, м'],
  ['required_lift_height_m', 'Требуемая высота подъёма, м'], ['ceiling_height_m', 'Высота потолка, м'],
  ['floor_flatness_mm_2m', 'Неровность пола на 2 м, мм'], ['max_slope_percent', 'Уклон маршрута, %'],
  ['available_charging_power_kw', 'Доступная мощность зарядки, кВт'],
];

export const objectConstraintLabel = key => Object.fromEntries(OBJECT_CONSTRAINT_FIELDS)[key]
  || {outdoor_required:'Работа на улице', floor_covering:'Покрытие пола'}[key] || key;

export function buildObjectConstraintContext(zone, process) {
  const data = zone?.objectConstraints;
  if (!data) return null;
  const values = Object.fromEntries(Object.entries(data.values || {}).filter(([, value]) => value !== '' && value != null && value !== false));
  if (Object.keys(values).length && !data.confirmed) throw new Error('Подтвердите структурированные ограничения зоны.');
  const context = { object_kind: process.object_kind, ...values, requirement_sources: {} };
  if (process.item_mass?.status === 'KNOWN' && context.max_payload_kg == null) {
    throw new Error('Подтвердите требуемую грузоподъёмность партии за рейс.');
  }
  if (process.item_mass?.status === 'KNOWN' && context.max_payload_kg != null) {
    const units = process.explicit_batch?.status === 'KNOWN' ? Number(process.explicit_batch.normalized_value) : 1;
    if (Number(context.max_payload_kg) < Number(process.item_mass.normalized_value) * units) {
      throw new Error('Требуемая грузоподъёмность ниже массы перевозимой партии.');
    }
  }
  for (const field of Object.keys(context).filter(key => !['object_kind', 'requirement_sources'].includes(key))) {
    context.requirement_sources[field] = { kind: 'USER', user_confirmed: true, source_ref: `object.${zone.zoneId}.${field}.${process.input_revision}` };
  }
  return context;
}
