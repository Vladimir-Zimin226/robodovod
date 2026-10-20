"""Exercise the standalone RobCraft construction entry point in a local browser."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket


ROOT = Path(__file__).resolve().parent / "evidence"
ROOT.mkdir(exist_ok=True)
pages = requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
page = next(item for item in pages if item.get("type") == "page")
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
sequence = 0


def call(method, params=None):
    global sequence
    sequence += 1
    current = sequence
    ws.send(json.dumps({"id": current, "method": method, "params": params or {}}))
    while True:
        response = json.loads(ws.recv())
        if response.get("id") == current:
            if "error" in response:
                raise RuntimeError(response["error"])
            return response.get("result", {})


def evaluate(expression):
    result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True})["result"]
    if result.get("exceptionDetails"):
        raise RuntimeError(result["exceptionDetails"])
    return result.get("value")


def until(expression, label):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if evaluate(expression):
            return
        time.sleep(.2)
    raise RuntimeError(f"Timed out: {label}")


try:
    call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
    call("Page.navigate", {"url": "http://127.0.0.1:4174/"})
    until("Boolean(document.querySelector('#world-form') && document.querySelector('[data-start=empty]'))", "launcher")
    until("Boolean(document.querySelector('#build-catalog button'))", "RobCraft initialization")
    assert not evaluate("document.querySelector('.launcher-advanced').open")
    assert evaluate("document.querySelectorAll('[data-start]').length") == 4
    evaluate("document.querySelector('[data-start=mine]').click()")
    assert evaluate("document.querySelector('#saved-scene-status').textContent.length") > 0
    evaluate("document.querySelector('[data-start=empty]').click()")
    data = call("Page.captureScreenshot", {"format": "png"})["data"]
    (ROOT / "robcraft-launcher.png").write_bytes(base64.b64decode(data))
    evaluate("document.querySelector('#world-form button[type=submit]').click()")
    until("!document.querySelector('#hud').classList.contains('hidden')", "world start")
    assert evaluate("document.body.classList.contains('editor-active')")
    assert not evaluate("document.querySelector('#craft-toolbar').classList.contains('hidden')")
    assert evaluate("document.querySelector('#editor-panel').classList.contains('hidden')")
    assert evaluate("document.querySelector('#camera-mode').textContent.includes('АВТОПОКАЗ')") is False
    evaluate("document.querySelector('#inventory-toggle').click()")
    assert not evaluate("document.querySelector('#editor-panel').classList.contains('hidden')")
    data = call("Page.captureScreenshot", {"format": "png"})["data"]
    (ROOT / "robcraft-catalog.png").write_bytes(base64.b64decode(data))
    evaluate("document.querySelector('#view-toggle').click()")
    assert evaluate("!document.querySelector('#craft-map').classList.contains('hidden')")
    data = call("Page.captureScreenshot", {"format": "png"})["data"]
    (ROOT / "robcraft-plan.png").write_bytes(base64.b64decode(data))
    print("PASS: launcher, construction, manual camera, catalog i, 2D map")
finally:
    call("Emulation.clearDeviceMetricsOverride")
    ws.close()
