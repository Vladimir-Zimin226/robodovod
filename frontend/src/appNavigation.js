const PHASE_HASH = Object.freeze({
  onboarding: '', process: '#assistant', model: '#model', intake: '#calculation', robots: '#robots', simulation: '#simulation', money: '#money', catalog: '#catalog', craft: '#craft',
  results: '#results', reports: '#reports', projects: '#projects', account: '#account', admin: '#admin',
  guestDemo: '#demo-warehouse', expert: '#roboexpert', economics: '#economics', economicsMethodology: '#economics-methodology',
  templates: '#templates', adminCatalog: '#admin-catalog',
});

const HASH_PHASE = Object.fromEntries(Object.entries(PHASE_HASH).map(([phase, hash]) => [hash, phase]));

export function phaseHash(phase) {
  if (!Object.hasOwn(PHASE_HASH, phase)) throw new TypeError(`Неизвестная страница: ${phase}`);
  return PHASE_HASH[phase];
}

export function phaseFromHash(hash, hasResult = false) {
  if (['#demo-warehouse', '#templates', '#assistant', '#model', '#roboexpert', '#variants', '#scenarios', '#robo-expert', '#process'].includes(hash)) return 'onboarding';
  const phase = hash === '#process' ? 'process' : hash === '#report' ? 'reports'
    : ['#variants', '#scenarios', '#robo-expert'].includes(hash) ? 'expert' : HASH_PHASE[hash] || 'onboarding';
  return ['robots', 'simulation', 'money', 'results'].includes(phase) && !hasResult ? 'onboarding' : phase;
}
