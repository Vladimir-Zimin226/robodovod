"""F7 production-build browser smoke with synthetic, read-only API replies."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("F7_BROWSER_OUT", str(ROOT / "docs" / "planning" / "assets" / "f7")))
OUT.mkdir(parents=True, exist_ok=True)
WEB = os.environ.get("F7_BROWSER_WEB", "http://127.0.0.1:5177")
BROWSERS = {
    "chrome": Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    "edge": Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
}
INJECT = r"""
(() => {
  sessionStorage.setItem('robodovod.active-project.user-f7', 'project-b');
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, options) => {
    const url = String(input && input.url ? input.url : input);
    let value;
    if (url.endsWith('/api/auth/me')) value = {user: {id: 'user-f7', email: 'f7@example.invalid',
      name: 'Проверка F7', role: sessionStorage.getItem('f7-role') || 'ADMIN'}};
    else if (url.endsWith('/api/projects')) value = {items: [
      {id: 'project-a', name: 'Склад А', scenarios: []},
      {id: 'project-b', name: 'Склад Б', scenarios: []}]};
    else if (url.endsWith('/api/admin/catalog')) value = {versions: [], active: []};
    if (value) return Promise.resolve(new Response(JSON.stringify(value),
      {status: 200, headers: {'Content-Type': 'application/json'}}));
    if (url.includes('/api/')) return Promise.resolve(new Response('{}',
      {status: 404, headers: {'Content-Type': 'application/json'}}));
    return nativeFetch(input, options);
  };
})();
"""


def run_browser(name: str, binary: Path) -> dict:
    profile = Path(tempfile.mkdtemp(prefix=f"f7-{name}-", dir=ROOT / ".tmp"))
    process = subprocess.Popen([str(binary), "--headless=new", "--no-first-run",
        "--remote-allow-origins=*", "--remote-debugging-port=0", "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader", f"--user-data-dir={profile}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    seq = 0

    def call(method: str, params: dict | None = None) -> dict:
        nonlocal seq
        seq += 1
        ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            result = json.loads(ws.recv())
            if result.get("id") == seq:
                assert not result.get("error"), result
                return result.get("result", {})

    def js(source: str):
        result = call("Runtime.evaluate", {"expression": source, "returnByValue": True,
                                           "awaitPromise": True})
        assert not result.get("exceptionDetails"), result
        return result.get("result", {}).get("value")

    def until(source: str):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                value = js(source)
                if value:
                    return value
            except (AssertionError, websocket.WebSocketTimeoutException):
                pass
            time.sleep(.15)
        raise AssertionError(f"{name}: timed out: {source}; hash={js('location.hash')}; body={js('document.body.innerText.slice(0, 500)')}")

    try:
        deadline = time.monotonic() + 20
        while not (profile / "DevToolsActivePort").exists():
            assert time.monotonic() < deadline, f"{name} failed to launch"
            time.sleep(.1)
        port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
        pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        ws = websocket.create_connection(next(page["webSocketDebuggerUrl"] for page in pages if page["type"] == "page"), timeout=20)
        call("Runtime.enable")
        call("Page.enable")
        call("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
        call("Emulation.setDeviceMetricsOverride", {"width": 1366, "height": 768,
                                                    "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": f"{WEB}/#templates"})
        until("document.querySelector('[aria-label=\"Шаблоны и загрузка данных\"]') !== null")
        until("document.querySelector('.project-context strong')?.textContent === 'Склад Б'")
        assert js("document.querySelector('nav[aria-label=\"Проект и данные\"] button.active')?.textContent.includes('Шаблоны')")
        assert js("document.querySelector('nav[aria-label=\"Администрирование\"] button')?.textContent.includes('Каталог')")
        js("document.querySelector('nav[aria-label=\"Администрирование\"] button').click()")
        until("location.hash === '#admin-catalog' && document.querySelector('[aria-label=\"Администрирование каталога\"]') !== null")
        assert js("document.querySelector('.project-context strong').textContent") == "Склад Б"
        (OUT / f"{name}-admin.png").write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        js("history.back()")
        until("location.hash === '#templates' && document.querySelector('[aria-label=\"Шаблоны и загрузка данных\"]') !== null")
        assert js("document.querySelector('.project-context strong').textContent") == "Склад Б"
        call("Page.reload")
        until("document.querySelector('.project-context strong')?.textContent === 'Склад Б'")
        assert js("location.hash") == "#templates"
        (OUT / f"{name}-templates.png").write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844,
                                                    "deviceScaleFactor": 1, "mobile": True})
        until("document.querySelector('.mobile-menu-button') !== null")
        js("document.querySelector('.mobile-menu-button').click()")
        until("document.querySelector('.app-sidebar.is-open') !== null")
        assert js("document.querySelector('nav[aria-label=\"Проект и данные\"]')?.textContent.includes('Шаблоны')")
        assert js("document.querySelector('nav[aria-label=\"Администрирование\"]')?.textContent.includes('Каталог')")
        (OUT / f"{name}-mobile-menu.png").write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        js("sessionStorage.setItem('f7-role', 'USER'); location.hash = '#admin-catalog'")
        call("Page.reload")
        until("document.body.innerText.includes('Требуется учётная запись администратора.')")
        assert not js("document.querySelector('nav[aria-label=\"Администрирование\"]')")
        assert js("document.querySelector('.project-context strong').textContent") == "Склад Б"
        return {"browser": name, "direct_link": True, "back": True, "reload": True,
                "project_restored": True, "admin_denied_explained": True}
    finally:
        if ws:
            ws.close()
        process.terminate()
        process.wait(timeout=10)


def main() -> None:
    html = requests.get(WEB, timeout=10)
    assert html.status_code == 200
    assert '<meta name="theme-color" content="#0a1217"' in html.content.decode("utf-8")
    assert '<title>РОБОДОВОД — предварительное ТЭО роботизации</title>' in html.content.decode("utf-8")
    for asset in ("favicon.svg", "favicon-32.png", "favicon.ico"):
        response = requests.get(f"{WEB}/{asset}", timeout=10)
        assert response.status_code == 200, asset
        assert "text/html" not in response.headers.get("Content-Type", ""), asset
    results = [run_browser(name, binary) for name, binary in BROWSERS.items()]
    (OUT / "report.json").write_text(json.dumps({"mode": "synthetic API; production Vite build",
        "assets_http_200": ["favicon.svg", "favicon-32.png", "favicon.ico"],
        "theme_color": "#0a1217", "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS", results)


if __name__ == "__main__":
    main()
