import presets from './showcasePresets.json' with { type: 'json' };

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

export const SHOWCASE_PRESETS = deepFreeze(presets);

export function buildShowcaseInput(objectType) {
  const preset = SHOWCASE_PRESETS[objectType];
  if (!preset || preset.mode !== 'DEMO_LOCKED' || !preset.input?.roles?.length) {
    throw new Error('Данные готового примера неполны');
  }
  return structuredClone(preset.input);
}
