const API = import.meta.env?.VITE_API_URL || '';

function errorMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map((item) => item.msg).join('; ');
  return fallback;
}

export async function persistenceRequest(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: 'include',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(errorMessage(payload, `HTTP ${response.status}`));
  }
  if (response.status === 204) return null;
  return response.json();
}

export function readCsrfCookie() {
  const item = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('robodovod_csrf='));
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : '';
}
