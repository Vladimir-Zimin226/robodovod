"""Targeted local browser smoke for the guest-to-registration calculation path."""

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from local_browser import LocalBrowser


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
OUTPUT = ROOT / ".tmp" / "mobile-guest-registration"

FAKE_API = r"""
window.__browserErrors = [];
window.addEventListener('error', event => window.__browserErrors.push(event.message));
window.__testFetches = [];
const originalFetch = window.fetch.bind(window);
window.__testProjects = new URLSearchParams(location.search).has('existing')
  ? [{id: 'existing-project', name: 'Существующий проект',
      scenarios: [{id: 'base', slot: 'BASE', name: 'Базовый', inputs: null}]}] : [];
window.fetch = (input, options = {}) => {
  const path = new URL(typeof input === 'string' ? input : input.url, location.href).pathname;
  const method = options.method || 'GET';
  window.__testFetches.push(`${method} ${path}`);
  const reply = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {
    status, headers: {'Content-Type': 'application/json'}
  }));
  if (path === '/api/auth/me') return reply({}, 401);
  if (path === '/api/auth/register' || path === '/api/auth/login')
    return reply({user: {id: 'browser-user', email: 'browser@example.test', role: 'USER'}, csrf_token: 'test'});
  if (path === '/api/projects' && method === 'GET') return reply({items: window.__testProjects});
  if (path === '/api/projects' && method === 'POST') {
    const project = {id: 'browser-project', name: JSON.parse(options.body).name,
      scenarios: [{id: 'base', slot: 'BASE', name: 'Базовый', inputs: null}]};
    window.__testProjects.push(project);
    return reply(project);
  }
  if (path === '/api/v2/calculation-intake/normalize') {
    const request = JSON.parse(options.body);
    return reply({schema_version: 'calculation-intake-normalization-v2',
      input_revision: request.input_revision, valid: true, required_inputs: [], errors: [],
      normalized_processes: request.processes.filter(item => item.active).map(item => ({
        ...item, object_kind: request.object_kind, scope: 'TRANSPORT_CYCLE'
      }))});
  }
  if (path.includes('/operation-batches') || path.includes('/capacity-catalog/positions'))
    return reply({items: []});
  if (path.startsWith('/api/')) return reply({items: []});
  return originalFetch(input, options);
};
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def check(width, server_port, existing_project=False):
    browser = LocalBrowser(f"http://127.0.0.1:{server_port}/index.html?setup=1", OUTPUT)
    try:
        browser.call("Page.enable")
        browser.call("Runtime.enable")
        browser.call("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": 850, "deviceScaleFactor": 1, "mobile": width < 600,
        })
        browser.call("Page.addScriptToEvaluateOnNewDocument", {"source": FAKE_API})
        query = "?existing=1" if existing_project else ""
        browser.call("Page.navigate", {"url": f"http://127.0.0.1:{server_port}/{query}#demo-warehouse"})
        browser.until("Boolean(document.querySelector('.guest-warehouse-demo'))")
        assert browser.js("Array.isArray(window.__testFetches)"), "Fake API was not installed"
        if width < 600:
            assert browser.js("Boolean(document.querySelector('.mobile-account-action')?.getClientRects().length)")
            assert browser.js("document.querySelector('.mobile-account-action').textContent.includes('регистрация')")
        else:
            assert browser.js("Boolean(document.querySelector('.user-avatar')?.getClientRects().length)")

        browser.js("[...document.querySelectorAll('button')].find(x => x.textContent.includes('Открыть ввод своего процесса')).click()")
        browser.until("Boolean(document.querySelector('.typical-object-action'))")
        browser.js("document.querySelector('.typical-object-action').click()")
        original_area = browser.js("document.getElementById('intake-facility.totalArea').value")
        assert original_area
        browser.js("[...document.querySelectorAll('button')].find(x => x.textContent.trim() === 'Проверить ввод').click()")
        try:
            browser.until("Boolean(document.querySelector('.preliminary-section'))", timeout=5)
        except AssertionError as error:
            raise AssertionError((error, browser.js("window.__testFetches"), browser.js("window.__browserErrors"))) from error
        assert browser.js("document.querySelector('.preliminary-section').textContent.includes('Зарегистрироваться для расчёта')")
        browser.js("[...document.querySelectorAll('.preliminary-section button')].find(x => x.textContent.includes('Зарегистрироваться для расчёта')).click()")
        browser.until("Boolean(document.querySelector('.auth-tabs button.active'))")
        assert browser.js("document.querySelector('.auth-tabs button.active').textContent.trim()") == "Регистрация"
        if existing_project:
            browser.js("[...document.querySelectorAll('.auth-tabs button')].find(x => x.textContent.trim() === 'Вход').click()")
        browser.js("{ const fill = (selector, value) => { const el = document.querySelector(selector); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, value); el.dispatchEvent(new Event('input', {bubbles: true})); }; fill('input[type=email]', 'browser@example.test'); fill('input[type=password]', 'test-password-123'); }")
        browser.js("document.querySelector('.persistence-form').requestSubmit()")
        browser.until("Boolean(document.querySelector('.typical-object-action'))")
        assert browser.js("document.getElementById('intake-facility.totalArea').value") == original_area
        if existing_project:
            browser.until("document.querySelector('.project-context strong')?.textContent === 'Существующий проект'")
        else:
            browser.js("[...document.querySelectorAll('button')].find(x => x.textContent.trim() === 'Создать проект').click()")
            browser.until("Boolean(document.querySelector('.inline-create'))")
            browser.js("{ const el = document.querySelector('.inline-create input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, 'Проверка склада'); el.dispatchEvent(new Event('input', {bubbles: true})); document.querySelector('.inline-create').requestSubmit(); }")
            browser.until("Boolean(document.querySelector('.typical-object-action'))")
        assert browser.js("document.getElementById('intake-facility.totalArea').value") == original_area
        assert browser.js("Boolean(document.querySelector('.preliminary-section'))")
        assert browser.js("document.documentElement.scrollWidth <= innerWidth")
        assert browser.js("window.__browserErrors.length") == 0
        return {"width": width, "existing_project": existing_project, "guest_draft_preserved": True,
                "project_return": True, "no_blank_screen": True}
    finally:
        browser.close()


if __name__ == "__main__":
    assert (DIST / "index.html").exists(), "Run npm run build first"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(DIST)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cases = [(320, False), (390, False), (1366, False), (390, True)]
        print(json.dumps([check(width, server.server_port, existing) for width, existing in cases], ensure_ascii=False))
    finally:
        server.shutdown()
        thread.join()
