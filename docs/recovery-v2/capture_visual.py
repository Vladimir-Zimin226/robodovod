"""Capture local component playback through a headless Chromium CDP port (default 9225)."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket


ROOT = Path(__file__).resolve().parent / "evidence"
ROOT.mkdir(exist_ok=True)
pages = requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
page = next((item for item in pages if item.get("type") == "page"
             and "/qa/recovery/index.html" in item.get("url", "")),
            next(item for item in pages if item.get("type") == "page"))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15,
                                  suppress_origin=True)
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
    return call("Runtime.evaluate", {"expression": expression, "returnByValue": True})["result"].get("value")


call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900,
                                             "deviceScaleFactor": 1, "mobile": False})


def capture(name):
    evaluate("document.querySelector('.scene-preview')?.scrollIntoView({block: 'center'})")
    time.sleep(.25)
    image = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
    (ROOT / name).write_bytes(base64.b64decode(image))


for kind in ("warehouse", "airport", "clinic"):
    call("Page.navigate", {"url": f"http://127.0.0.1:4175/qa/recovery/index.html?kind={kind}"})
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        ready = evaluate("document.querySelector('[data-glb-status]')?.dataset.glbStatus")
        current_kind = evaluate("new URLSearchParams(location.search).get('kind')")
        if ready == "READY" and current_kind == kind:
            break
        time.sleep(.25)
    else:
        raise RuntimeError(f"{kind}: GLB did not load")
    evaluate("document.querySelector('.scene-sim-controls button[type=submit]').click()")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if evaluate("Boolean(document.querySelector('.scene-playback-controls'))"):
            break
        time.sleep(.1)
    else:
        raise RuntimeError(f"{kind}: click did not start playback")
    evaluate("document.querySelector('.scene-playback-controls button').click()")  # Pause.
    time.sleep(.15)
    start = evaluate("document.querySelector('#recovery-pose')?.textContent")
    capture(f"sim-{kind}-start.png")
    time.sleep(.5)
    paused = evaluate("document.querySelector('#recovery-pose')?.textContent")
    if paused != start:
        raise RuntimeError(f"{kind}: pause did not freeze the pose")
    evaluate("document.querySelector('.scene-playback-controls button').click()")  # Resume.
    time.sleep(4)
    evaluate("document.querySelector('.scene-playback-controls button').click()")
    end = evaluate("document.querySelector('#recovery-pose')?.textContent")
    capture(f"sim-{kind}-after-4s.png")
    print(f"{kind}: {start} -> {end}")
    if not end or start == end:
        raise RuntimeError(f"{kind}: pose did not move")
ws.close()
