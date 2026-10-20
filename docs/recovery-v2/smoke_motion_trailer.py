"""Browser smoke for the real video player, chapter seeking and local motion export."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path(__file__).resolve().parent / "evidence"
page = next(item for item in requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
            if item.get("type") == "page")
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15,
                                 suppress_origin=True)
serial = 0


def call(method, params=None):
    global serial
    serial += 1
    current = serial
    ws.send(json.dumps({"id": current, "method": method, "params": params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get("id") == current:
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("result", {})


def evaluate(expression):
    return call("Runtime.evaluate", {"expression": expression,
                                      "returnByValue": True})["result"].get("value")


try:
    call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800,
                                                "deviceScaleFactor": 1, "mobile": False})
    call("Page.navigate", {"url": "http://127.0.0.1:4175/"})
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        if evaluate("Boolean(document.querySelector('.trailer-preview button'))"):
            break
        time.sleep(.2)
    else:
        raise RuntimeError("trailer preview did not render")
    evaluate("document.querySelector('.trailer-preview button').click()")
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        state = evaluate("JSON.stringify((()=>{const v=document.querySelector('.trailer-dialog video'); return v && {duration:v.duration,width:v.videoWidth,height:v.videoHeight,ready:v.readyState,time:v.currentTime}})())")
        state = json.loads(state) if state else None
        if state and state["ready"] >= 2 and 17.9 <= state["duration"] <= 18.1:
            break
        time.sleep(.2)
    else:
        raise RuntimeError(f"trailer video not ready: {state}")
    if (state["width"], state["height"]) != (1280, 720):
        raise RuntimeError(f"wrong trailer dimensions: {state}")
    evaluate("document.querySelectorAll('.trailer-dialog nav button')[2].click()")
    time.sleep(.6)
    position = evaluate("document.querySelector('.trailer-dialog video').currentTime")
    if not 12 <= position < 15:
        raise RuntimeError(f"clinic chapter seek failed: {position}")
    image = call("Page.captureScreenshot", {"format": "png"})["data"]
    (OUT / "trailer-player-clinic.png").write_bytes(base64.b64decode(image))
    print(f"PASS: video {state['width']}x{state['height']} / {state['duration']} s; clinic seek {position:.1f} s")
finally:
    call("Emulation.clearDeviceMetricsOverride")
    ws.close()
