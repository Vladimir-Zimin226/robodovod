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

export function matchesCalculationParticipation(robot, participation) {
  if (participation === 'participating') return robot.calculation_ready === true;
  if (participation === 'requires_data') return robot.calculation_ready !== true;
  return true;
}

export function filterAndSortCatalog(robots, filters) {
  const filtered = robots.filter((robot) => {
    if (filters.family && robot.system_family !== filters.family) return false;
    if (filters.type && robot.type_code !== filters.type) return false;
    if (filters.manufacturer && robot.manufacturer !== filters.manufacturer) return false;
    return matchesCalculationParticipation(robot, filters.calculationParticipation)
      && matchesCatalogQuery(robot, filters.query || '');
  });
  const key = filters.sort === 'manufacturer'
    ? (robot) => robot.manufacturer || ''
    : filters.sort === 'type'
      ? (robot) => robot.type_code || ''
      : (robot) => robot.name || '';
  return [...filtered].sort((left, right) => (
    key(left).localeCompare(key(right), 'ru')
    || (left.source_row_number || 0) - (right.source_row_number || 0)
  ));
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

export function formatCatalogFact(fact) {
  if (!fact || fact.value === null || fact.value === undefined) return '—';
  const value = typeof fact.value === 'object' ? JSON.stringify(fact.value) : String(fact.value);
  return `${value}${fact.unit ? ` ${fact.unit}` : ''}`;
}

export function runtimeBlockerLabel(blocker) {
  if (blocker === 'capacity_runtime') return 'Нет материализованного capacity-профиля';
  if (blocker === 'capacity_runtime:invalid_contract') return 'Capacity-профиль не прошёл проверку контракта';
  if (blocker === 'unsupported_capacity_profile') return 'Тип решения пока не поддержан расчётом мощности';
  if (blocker === 'not_equipment') return 'Позиция не является рассчитываемым оборудованием';
  if (blocker === 'calculation_facts_incomplete') return 'Не хватает доказанных расчётных характеристик';
  if (blocker.startsWith('missing:')) return 'Не хватает доказанной расчётной характеристики';
  if (blocker.startsWith('conflict:')) return 'Расчётная характеристика требует разрешения конфликта';
  if (blocker === 'runtime_projection') return 'Нет утверждённой runtime-проекции';
  if (blocker === 'runtime_projection:economics') return 'Не хватает экономических параметров';
  if (blocker === 'runtime_projection:invalid_robot_contract') return 'Runtime-профиль не прошёл проверку контракта';
  if (blocker === 'procurement_option:ambiguous_purchase_amount') return 'Цена приобретения неоднозначна';
  if (blocker.startsWith('matching_fact:')) return 'Не хватает проверенной характеристики для matching';
  return 'Позиция пока недоступна для расчёта';
}

export function catalogDetailView(position) {
  const applicability = position.applicability?.[0] || {};
  const fields = position.enrichment?.fields || {};
  const provenance = position.enrichment?.provenance || {};
  const sourcePage = provenance.source_page ?? position.media?.source_page;
  const sourceSlot = provenance.source_slot ?? position.media?.source_slot;
  const trl = Number.isFinite(fields.trl) ? `${fields.trl}/9` : Number.isFinite(position.trl) ? `${position.trl}/9` : null;
  const marketPotential = Number.isFinite(fields.market_potential) ? `${fields.market_potential}/5` : null;
  let sourceUrl = null;
  try {
    const candidate = new URL(fields.source_url);
    if (candidate.protocol === 'http:' || candidate.protocol === 'https:') sourceUrl = candidate.href;
  } catch {
    sourceUrl = null;
  }
  return {
    description: position.description || 'Описание модели в исходном каталоге не указано.',
    industries: position.industries || (applicability.industry ? [applicability.industry] : []),
    useCases: position.use_cases || (applicability.scenario ? [applicability.scenario] : []),
    regions: position.regions || (applicability.region ? [applicability.region] : []),
    caseText: applicability.case || null,
    trl,
    lifecycleStage: fields.lifecycle_stage || position.maturity_status || null,
    marketPotential,
    serviceLabels: fields.service_labels || [],
    sourceUrl,
    sourceLocation: sourcePage ? `страница ${sourcePage}${sourceSlot ? `, слот ${sourceSlot}` : ''}` : null,
    limitation: provenance.limitation || null,
    facts: position.facts || [],
    purchase: position.purchase || null,
    purchasePrice: position.purchase?.raw_price || formatCatalogPrice(normalizeOfficialModel(position)),
    runtimeBlockers: position.runtime_blockers || [],
    calculationBlockers: position.calculation_blockers || [],
    calculationAssumptions: position.calculation_assumptions || [],
    calculationVendorFacts: position.calculation_vendor_facts || [],
    calculationProvenance: position.calculation_provenance || null,
  };
}
