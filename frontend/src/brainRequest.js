// Server MODEL_WAIT_SECONDS is 59; allow time for persistence and transport.
export const BRAIN_REQUEST_TIMEOUT_MS = 70000;

export async function brainRequest(url, options = {}, timeoutMs = BRAIN_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const cancel = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) cancel();
  options.signal?.addEventListener('abort', cancel, { once: true });
  const timer = setTimeout(() => controller.abort(new DOMException('Время ожидания истекло', 'TimeoutError')), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
    return payload;
  } catch (error) {
    if (controller.signal.aborted && !options.signal?.aborted) {
      throw new Error('Истекло время ожидания. Проверяем сохранённый статус; сервер мог продолжить обработку. Можно исправить поля вручную.', { cause: error });
    }
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', cancel);
  }
}
