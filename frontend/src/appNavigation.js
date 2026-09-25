const PHASE_HASH = Object.freeze({
  onboarding: '', process: '#assistant', intake: '#calculation', catalog: '#catalog',
  results: '#results', projects: '#projects', account: '#account', admin: '#admin',
  guestDemo: '#demo-warehouse',
});

const HASH_PHASE = Object.fromEntries(Object.entries(PHASE_HASH).map(([phase, hash]) => [hash, phase]));

export function phaseHash(phase) {
  if (!Object.hasOwn(PHASE_HASH, phase)) throw new TypeError(`Неизвестная страница: ${phase}`);
  return PHASE_HASH[phase];
}

export function phaseFromHash(hash, hasResult = false) {
  const phase = hash === '#process' ? 'process' : HASH_PHASE[hash] || 'onboarding';
  return phase === 'results' && !hasResult ? 'onboarding' : phase;
}
