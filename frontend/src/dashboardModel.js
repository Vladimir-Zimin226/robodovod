export const SCENARIO_LABELS = {
  pessimistic: 'Пессимистичный',
  base: 'Базовый',
  optimistic: 'Оптимистичный',
};

export { formatServerQuantity, getCapacityResultsModel } from './capacityResultsModel.js';

export function getRecommended(recommendations = []) {
  return recommendations.find((item) => item.is_best === true) || null;
}

export function getScenario(recommendation, scenario = 'base') {
  if (!recommendation) return null;
  return (
    recommendation.scenarios?.find((item) => item.scenario === scenario) ||
    null
  );
}

export function getDashboardModel(result, userInput, scenario = 'base') {
  const recommendations = result?.recommendations || [];
  const recommended = getRecommended(recommendations);
  const economics = getScenario(recommended, scenario);
  const dataQuality = result?.data_quality || {};
  const scenarioSpec = result?.scenario_spec || null;
  const contractZone = scenarioSpec?.zones?.[0] || null;
  const fleet = scenarioSpec?.fleet || [];
  const topWarnings = [
    ...(result?.warnings || []),
    ...(recommended?.warnings || []),
  ];

  return {
    recommended,
    economics,
    recommendations,
    hasAcceptableRecommendation: Boolean(recommended),
    status: recommended ? recommended.economic_status : 'NO_ACCEPTABLE_ECONOMICS',
    readiness: recommended?.readiness_score ?? null,
    confidence: recommended?.price_confidence ?? scenarioSpec?.economics?.confidence ?? null,
    dataCompleteness: dataQuality.completeness_pct ?? null,
    dataQualityLevel: dataQuality.level || null,
    fleetSize: economics?.quantity ?? recommended?.quantity ?? fleet.reduce((sum, item) => sum + item.quantity, 0),
    fleetUtilization: economics?.utilization ?? recommended?.fleet_utilization ?? null,
    baseline: result?.manual_baseline || null,
    fteTotal: userInput?.staff_headcount ?? result?.manual_baseline?.manual_fte ?? null,
    fteReleased: recommended?.fte_released ?? null,
    fteRetained: recommended?.fte_retained ?? null,
    processType: userInput?.process_type || contractZone?.process_type || null,
    facilityArea: userInput?.area_m2 ?? scenarioSpec?.facility?.area_m2 ?? null,
    region: userInput?.region || userInput?.site_location || null,
    warning: topWarnings[0] || null,
    revisionId: result?.revision_id || scenarioSpec?.revision_id || null,
  };
}
