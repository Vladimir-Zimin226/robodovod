export function catalogItemKey(item) {
  return item.position_id || item.id;
}

export function normalizeOfficialModel(model) {
  const specs = Object.fromEntries((model.facts || []).map((fact) => [fact.code, fact.value]));
  return {
    ...model,
    catalog_key: catalogItemKey(model),
    category: model.system_family,
    type_label: model.type_code,
    purpose: model.use_cases || [],
    specs,
    fact_list: model.facts || [],
    economics: model.purchase ? { robot_capex_rub: model.purchase.amount } : {},
    price: {
      basis: model.purchase ? 'official_catalog' : 'quote_required',
      note: model.purchase?.evidence_id ? `Evidence: ${model.purchase.evidence_id}` : 'Цена отсутствует',
    },
  };
}

export function matchesCatalogQuery(robot, query) {
  const needle = query.trim().toLocaleLowerCase('ru-RU');
  if (!needle) return true;
  return [robot.name, robot.manufacturer, robot.type_code, robot.description, robot.source_record_key,
    ...(robot.industries || []), ...(robot.use_cases || []), ...(robot.regions || [])]
    .filter(Boolean)
    .some((value) => String(value).toLocaleLowerCase('ru-RU').includes(needle));
}

export function catalogMedia(model) {
  const media = model.media;
  if (!media?.url) return null;
  return {
    src: media.url,
    width: media.width_px || undefined,
    height: media.height_px || undefined,
    type: media.media_type || undefined,
  };
}

export function formatCatalogPrice(robot) {
  if (robot.price?.basis === 'quote_required') return 'По запросу';
  const value = robot.economics?.robot_capex_rub;
  if (!Number.isFinite(value)) return '—';
  if (value >= 1_000_000) return `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ₽`;
  return `${value.toLocaleString('ru-RU')} ₽`;
}
