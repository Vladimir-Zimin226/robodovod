export const candidateReason = {
  PRICE_NOT_CONFIRMED: 'цена не подтверждена',
  RESEARCH_NOT_PURCHASE_READY: 'исследовательская разработка',
  NO_SUPPORTED_CALCULATION_FORMULA: 'нет поддержанной формулы',
  CAPACITY_NOT_COMPUTED: 'парк не рассчитан',
  OTHER_OPERATION_OR_PHYSICAL_PROFILE: 'другой физический профиль',
};

export function recommendedCandidates(comparison, catalogItems) {
  const byId = new Map(catalogItems.map((item) => [item.position_id, item]));
  return (comparison?.candidates || [])
    .filter((row) => row.technical_score != null && row.status !== 'EXCLUDED' &&
      byId.get(row.position_id)?.selection?.status !== 'EXCLUDED')
    .sort((a, b) => Number(b.technical_score) - Number(a.technical_score) ||
      a.position_id.localeCompare(b.position_id));
}

export function catalogDiagnostics(items, comparison) {
  return {
    active: comparison?.catalog_position_count ?? null,
    process: items.length,
    profile: comparison?.profile_position_count ?? null,
    excluded: items.filter((item) => item.selection?.status === 'EXCLUDED').length,
    check: items.filter((item) => item.selection?.status === 'REQUIRES_CHECK').length,
    ready: items.filter((item) => item.selection?.calculation_compatible).length,
  };
}
