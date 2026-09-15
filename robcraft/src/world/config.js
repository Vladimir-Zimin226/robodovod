import { clamp } from '../core/math.js';

export const DEFAULT_CONFIG = Object.freeze({
  template: 'warehouse',
  seed: 'ROBODOVOD-2026',
  width: 48,
  depth: 38,
  rackRows: 5,
  robotCount: 4,
  occupancy: 72
});

export function normalizeConfig(source = {}, { extendedFleet = false } = {}) {
  const allowedTemplates = new Set(['warehouse', 'airport', 'hospital']);
  const template = allowedTemplates.has(source.template) ? source.template : DEFAULT_CONFIG.template;
  const robotCount = Math.round(clamp(Number(source.robotCount) || DEFAULT_CONFIG.robotCount, 1, extendedFleet ? 100 : 8));
  const requestedWidth = Math.round(clamp(Number(source.width) || DEFAULT_CONFIG.width, 32, extendedFleet ? 220 : 80));
  const parkingWidth = extendedFleet
    ? Math.ceil((robotCount - 1) * (template === 'warehouse' ? 2 : 1.5) + 12)
    : template === 'warehouse' ? Math.ceil((robotCount - 1) * 2 + 12) : 32;
  return {
    template,
    seed: String(source.seed || DEFAULT_CONFIG.seed).slice(0, 40),
    width: Math.max(requestedWidth, parkingWidth),
    depth: Math.round(clamp(Number(source.depth) || DEFAULT_CONFIG.depth, 26, extendedFleet ? 140 : 80)),
    rackRows: Math.round(clamp(Number(source.rackRows) || DEFAULT_CONFIG.rackRows, 3, 8)),
    robotCount,
    occupancy: Math.round(clamp(Number(source.occupancy) || DEFAULT_CONFIG.occupancy, 20, 95))
  };
}

export function configFromUrl(search = '') {
  const params = new URLSearchParams(search);
  const values = {};
  for (const key of Object.keys(DEFAULT_CONFIG)) {
    if (params.has(key)) values[key] = params.get(key);
  }
  return normalizeConfig({ ...DEFAULT_CONFIG, ...values });
}

export function configToQuery(config) {
  const params = new URLSearchParams();
  Object.entries(normalizeConfig(config)).forEach(([key, value]) => params.set(key, value));
  return `?${params.toString()}`;
}
