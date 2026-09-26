"""Local production-build smoke for catalog comparison on desktop and mobile."""

import json
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
WEB = "http://127.0.0.1:5177"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
INJECT = r"""
(() => {
  const items = [1, 2, 3].map((number) => ({
    id: `position-${number}`, name: `Модель ${number}`, manufacturer: 'Тест',
    system_family: 'BRS', type_code: 'AMR', source_row_number: number,
    calculation_ready: true, selection: {status: 'REQUIRES_CHECK', reasons: ['Нужна проверка']},
    facts: [], purchase: {amount: number * 1000000, evidence_id: 'synthetic'},
  }));
  const original = window.fetch.bind(window);
  window.fetch = (input, options) => {
    const url = String(input?.url || input);
    let body;
    if (url.endsWith('/api/auth/me')) body = {user: null};
    else if (url.includes('/api/catalog/models?')) body = {
      catalog: {code: 'synthetic', model_count: 3, position_count: 3,
        calculation_ready_model_count: 3, calculation_ready_position_count: 3},
      hierarchy: [{system_family: 'BRS', types: [{type_code: 'AMR', count: 3}]}],
      items, manufacturers: ['Тест'], maturities: [], availabilities: [], processes: [],
    };
    if (body) return Promise.resolve(new Response(JSON.stringify(body),
      {status: 200, headers: {'Content-Type': 'application/json'}}));
    if (url.includes('/api/')) return Promise.resolve(new Response('{}', {status: 404}));
    return original(input, options);
  };
})();
"""


def run(width):
    profile = Path(tempfile.mkdtemp(prefix="u2-compare-", dir=ROOT / ".tmp"))
    browser = subprocess.Popen([
        str(CHROME), "--headless=new", "--no-first-run", "--remote-allow-origins=*",
        "--remote-debugging-port=0", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
        f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
       creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    serial = 0

    def call(method, params=None):
        nonlocal serial
        serial += 1
        ws.send(json.dumps({"id": serial, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(ws.recv())
            if reply.get("id") == serial:
                assert "error" not in reply, reply
                return reply.get("result", {})

    def js(code):
        reply = call("Runtime.evaluate", {"expression": code, "returnByValue": True})
        assert "exceptionDetails" not in reply, reply
        return reply.get("result", {}).get("value")

    def until(code):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if js(code):
                return
            time.sleep(0.1)
        raise AssertionError((code, js("document.body.innerText.slice(0,500)")))

    try:
        deadline = time.monotonic() + 15
        while not (profile / "DevToolsActivePort").exists():
            assert time.monotonic() < deadline
            time.sleep(0.1)
        port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
        pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        ws = websocket.create_connection(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"), timeout=15)
        call("Runtime.enable")
        call("Page.enable")
        call("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
        call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 768, "deviceScaleFactor": 1, "mobile": width < 600})
        call("Page.navigate", {"url": WEB + "/#catalog"})
        until("document.querySelectorAll('.catalog-card-footer button').length === 3")
        js("document.querySelectorAll('.catalog-card-footer button')[0].click(); document.querySelectorAll('.catalog-card-footer button')[1].click()")
        until("document.querySelector('.catalog-footer-actions button')?.textContent.includes('Сравнить')")
        assert not js("document.querySelector('.catalog-compare-fab')")
        js("document.querySelector('.catalog-footer-actions button').click()")
        until("document.querySelector('[aria-labelledby=\"compare-title\"]') !== null")
        assert js("document.body.style.overflow") == "hidden"
        assert js("document.activeElement.getAttribute('aria-label')") == "Закрыть сравнение"
        call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
        call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape"})
        until("document.querySelector('[aria-labelledby=\"compare-title\"]') === null")
        assert js("document.body.style.overflow") == ""
        js("document.querySelector('.catalog-footer-actions button').click()")
        until("document.querySelector('[aria-labelledby=\"compare-title\"]') !== null")
        js("document.querySelector('.catalog-dialog-backdrop').dispatchEvent(new MouseEvent('mousedown', {bubbles: true}))")
        until("document.querySelector('[aria-labelledby=\"compare-title\"]') === null")
        js("document.querySelector('.catalog-footer-actions button').click()")
        until("document.querySelector('[aria-labelledby=\"compare-title\"]') !== null")
        js("history.pushState({}, '', '#calculation'); dispatchEvent(new PopStateEvent('popstate'))")
        until("document.querySelector('[aria-labelledby=\"compare-title\"]') === null && location.hash === '#calculation'")
        assert js("document.body.style.overflow") == ""
        js("history.back()")
        until("location.hash === '#catalog'")
        call("Page.reload")
        until("document.querySelectorAll('.catalog-card-footer button').length === 3")
        assert not js("document.querySelector('[aria-labelledby=\"compare-title\"]')")
        assert not js("document.documentElement.scrollWidth > innerWidth")
        return {"width": width, "escape": True, "backdrop": True, "navigation": True, "reload": True}
    finally:
        if ws:
            ws.close()
        browser.terminate()
        browser.wait(timeout=10)


if __name__ == "__main__":
    assert requests.get(WEB, timeout=5).ok
    print(json.dumps([run(1366), run(390)], ensure_ascii=False))
