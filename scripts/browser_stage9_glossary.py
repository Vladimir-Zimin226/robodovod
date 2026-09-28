"""Check the built glossary in desktop and mobile Chrome without a backend."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.request import urlopen

import websocket


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend/dist"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main() -> None:
    if not (DIST / "index.html").is_file() or not CHROME.is_file():
        raise RuntimeError("Build frontend and install Chrome before this browser check")
    handler = partial(QuietHandler, directory=str(DIST))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    profile = Path(tempfile.mkdtemp(prefix="stage9-chrome-", dir=ROOT))
    chrome = subprocess.Popen([str(CHROME), "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--remote-allow-origins=*", "--remote-debugging-port=0",
        f"--user-data-dir={profile}", "about:blank"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    seq = 0

    def call(method: str, params: dict | None = None) -> dict:
        nonlocal seq
        seq += 1
        ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            response = json.loads(ws.recv())
            if response.get("id") == seq:
                if response.get("error"):
                    raise RuntimeError(response["error"])
                return response.get("result", {})

    def js(source: str):
        result = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def until(source: str):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = js(source)
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(f"Timeout: {source}")

    try:
        active = profile / "DevToolsActivePort"
        for _ in range(100):
            if active.exists():
                break
            time.sleep(.1)
        if not active.exists():
            raise RuntimeError("Chrome DevTools did not start")
        port = active.read_text(encoding="utf-8").splitlines()[0]
        pages = json.load(urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3))
        ws = websocket.create_connection(next(page["webSocketDebuggerUrl"] for page in pages if page["type"] == "page"), timeout=5)
        web = f"http://127.0.0.1:{server.server_port}"
        call("Emulation.setDeviceMetricsOverride", {"width": 1366, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": f"{web}/#economics"})
        until("Boolean(document.querySelector('[aria-label=\"Экономика: справочник формул\"]'))")
        assert js("document.querySelectorAll('.economics-glossary-card').length") == 13
        assert js("document.querySelector('.app-nav [aria-current=page]').innerText") == "Экономика"
        for query, title, field in [("окупаемость", "Окупаемость", "discount_rate"),
                                    ("NPV", "Чистая приведённая стоимость", "discount_rate"),
                                    ("цена владения", "Стоимость владения", "horizon_years")]:
            source = """(() => {const input=document.querySelector('#economics-term-search');
                const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                set.call(input,%s);input.dispatchEvent(new Event('input',{bubbles:true}));return true})()""" % json.dumps(query, ensure_ascii=False)
            assert js(source)
            until("[...document.querySelectorAll('.economics-glossary-card')].some(x=>x.querySelector('summary strong')?.innerText===%s && x.open && x.innerText.includes(%s))" % (json.dumps(title, ensure_ascii=False), json.dumps(field)))
        assert js("document.querySelector('.economics-glossary-card[open] .economics-glossary-formula').textContent.includes('Формула')")
        assert js("Boolean(document.querySelector('.economics-methodology-invite button'))")
        assert js("(() => { document.querySelector('.economics-methodology-invite button').click(); return true })()")
        until("Boolean(document.querySelector('[aria-label=\"Полная методология оценки роботизации\"]'))")
        assert js("document.querySelectorAll('.methodology-chapter').length") == 16
        assert js("document.querySelector('.app-nav [aria-current=page]').innerText") == "Экономика"
        assert js("document.querySelector('.methodology-page').innerText.includes('Основной путь платформы сейчас не рассчитывает налог на прибыль')")
        assert js("document.querySelector('.methodology-page').innerText.includes('Комплектация не выводится из производительности штабелёра')")
        assert js("document.documentElement.scrollWidth <= innerWidth")
        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        call("Page.navigate", {"url": f"{web}/#economics-methodology"})
        until("document.querySelectorAll('.methodology-chapter').length===16")
        bounds = js("(() => {const e=document.querySelector('.methodology-page');return [innerWidth,e.getBoundingClientRect().left,e.getBoundingClientRect().right,document.documentElement.scrollWidth]})()")
        assert bounds[0] == 390 and bounds[1] >= 0 and bounds[2] <= 391 and bounds[3] <= 391, bounds
        assert js("(() => {document.querySelector('.methodology-back').click(); return true})()")
        until("document.querySelectorAll('.economics-glossary-card').length===13")
        print("Desktop glossary and 16-chapter methodology; 390 px mobile layout and return OK")
    finally:
        if ws is not None:
            ws.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
            chrome.wait(timeout=5)
        server.shutdown()
        server.server_close()
        if profile.resolve().is_relative_to(ROOT.resolve()) and profile.name.startswith("stage9-chrome-"):
            shutil.rmtree(profile)


if __name__ == "__main__":
    main()
