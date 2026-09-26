"""Check registration copy and viewport against the local production build."""

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


def run(width: int) -> dict:
    profile = Path(tempfile.mkdtemp(prefix="u5-register-", dir=ROOT / ".tmp"))
    process = subprocess.Popen([
        str(CHROME), "--headless=new", "--no-first-run", "--remote-allow-origins=*",
        "--remote-debugging-port=0", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
        f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    connection = None
    serial = 0

    def call(method, params=None):
        nonlocal serial
        serial += 1
        connection.send(json.dumps({"id": serial, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(connection.recv())
            if reply.get("id") == serial:
                assert "error" not in reply, reply
                return reply.get("result", {})

    def js(code):
        reply = call("Runtime.evaluate", {"expression": code, "returnByValue": True})
        assert "exceptionDetails" not in reply, reply
        return reply.get("result", {}).get("value")

    try:
        deadline = time.monotonic() + 15
        while not (profile / "DevToolsActivePort").exists():
            assert time.monotonic() < deadline
            time.sleep(0.1)
        port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
        pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        connection = websocket.create_connection(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"), timeout=15)
        call("Page.enable")
        call("Runtime.enable")
        call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.fetch=(input)=>Promise.resolve(new Response(JSON.stringify(String(input).endsWith('/api/auth/me')?{user:null}:{}),{status:200,headers:{'Content-Type':'application/json'}}));"})
        call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 768, "deviceScaleFactor": 1, "mobile": width < 600})
        call("Page.navigate", {"url": WEB + "/#account"})
        deadline = time.monotonic() + 15
        while not js("Boolean(document.querySelector('.auth-tabs button'))"):
            assert time.monotonic() < deadline
            time.sleep(0.1)
        js("[...document.querySelectorAll('.auth-tabs button')].find(x=>x.textContent.includes('Регистрация')).click()")
        assert js("document.querySelector('input[type=password]').minLength") == 12
        assert js("document.querySelector('.persistence-form small').textContent.trim()") == "Минимум 12 символов."
        assert js("document.documentElement.scrollWidth <= innerWidth")
        return {"width": width, "registration_copy": True, "no_horizontal_overflow": True}
    finally:
        if connection:
            connection.close()
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    assert requests.get(WEB, timeout=5).ok
    print(json.dumps([run(1366), run(390)], ensure_ascii=False))
