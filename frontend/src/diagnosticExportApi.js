export async function requestDiagnosticBundle(fetchImpl, csrfToken, baseUrl = '') {
  const response = await fetchImpl(`${baseUrl}/api/admin/diagnostics/export`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
  }
  return response.blob();
}
