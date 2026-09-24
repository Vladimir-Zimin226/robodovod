const API = import.meta.env?.VITE_API_URL || '';
const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED']);

function savedBase(request, analysisRunId) {
  return `/api/v2/simulations/projects/${encodeURIComponent(request.project_id)}/analysis-runs/${encodeURIComponent(analysisRunId)}`;
}

function readCsrfCookie() {
  const item = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('robodovod_csrf='));
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : '';
}

function exactState(value, request) {
  if (!value || value.schema_version !== 'simulation-run-state-v1') throw new TypeError('Неподдерживаемый ответ simulation API');
  if (value.request_id !== request.request_id
      || value.tenant_id !== request.tenant_id
      || value.project_id !== request.project_id
      || value.scenario_revision_id !== request.scenario_spec.revision_id) {
    throw new TypeError('Получен stale simulation response');
  }
  return value;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: 'include',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
  return payload;
}

export class SimulationApiSession {
  constructor({ pollMs = 250 } = {}) {
    this.pollMs = pollMs;
    this.generation = 0;
    this.current = null;
  }

  async start(request, onState = () => {}, analysisRunId = null) {
    this.generation += 1;
    const generation = this.generation;
    this.current = { request, analysisRunId };
    const base = analysisRunId ? savedBase(request, analysisRunId) : '/api/v2/simulations';
    const state = exactState(await api(base, {
      method: 'POST',
      headers: { 'X-CSRF-Token': readCsrfCookie() },
      body: JSON.stringify(request),
    }), request);
    if (generation !== this.generation) return null;
    onState(state);
    if (TERMINAL.has(state.state)) return state;
    return this.poll(request, generation, onState, analysisRunId);
  }

  async poll(request, generation, onState, analysisRunId = null) {
    const base = analysisRunId ? savedBase(request, analysisRunId) : '/api/v2/simulations';
    while (generation === this.generation) {
      await new Promise((resolve) => setTimeout(resolve, this.pollMs));
      if (generation !== this.generation) return null;
      const state = exactState(await api(`${base}/${encodeURIComponent(request.request_id)}`), request);
      if (generation !== this.generation) return null;
      onState(state);
      if (TERMINAL.has(state.state)) return state;
    }
    return null;
  }

  async cancel() {
    const current = this.current;
    if (!current) return null;
    const { request, analysisRunId } = current;
    this.generation += 1;
    this.current = null;
    const base = analysisRunId ? savedBase(request, analysisRunId) : '/api/v2/simulations';
    return exactState(await api(`${base}/${encodeURIComponent(request.request_id)}/cancel`, {
      method: 'POST', headers: { 'X-CSRF-Token': readCsrfCookie() },
    }), request);
  }

  async loadSaved(request, analysisRunId) {
    try {
      return exactState(await api(`${savedBase(request, analysisRunId)}/${encodeURIComponent(request.request_id)}`), request);
    } catch (error) {
      if (/not found/i.test(error.message)) return null;
      throw error;
    }
  }

  invalidate() {
    this.generation += 1;
    this.current = null;
  }
}
