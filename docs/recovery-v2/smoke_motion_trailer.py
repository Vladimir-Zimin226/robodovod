"""Browser smoke for the real video player, chapter seeking and local motion export."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path(__file__).resolve().parent / "evidence"
pages = requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
page = next(item for item in pages if item.get("type") == "page" and
            any(port in item.get("url", "") for port in (":4175/", ":4177/")))
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


def click(selector):
    evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center'}})")
    time.sleep(.5)
    coords = evaluate(f"JSON.stringify((()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})())")
    point = json.loads(coords)
    for kind in ("mousePressed", "mouseReleased"):
        call("Input.dispatchMouseEvent", {"type": kind, "x": point["x"], "y": point["y"], "button": "left", "clickCount": 1})


try:
    call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800,
                                                "deviceScaleFactor": 1, "mobile": False})
    call("Page.navigate", {"url": "http://127.0.0.1:4177/"})
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        if evaluate("Boolean(document.querySelector('.trailer-preview button'))"):
            break
        time.sleep(.2)
    else:
        raise RuntimeError("trailer preview did not render")
    preview = evaluate("JSON.stringify((()=>{const v=document.querySelector('.trailer-preview video'); return {muted:v.muted,loop:v.loop}})())")
    assert json.loads(preview) == {"muted": True, "loop": True}, preview
    click(".trailer-preview button")
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        state = evaluate("JSON.stringify((()=>{const v=document.querySelector('.trailer-dialog video'); return v && {duration:v.duration,width:v.videoWidth,height:v.videoHeight,ready:v.readyState,time:v.currentTime,paused:v.paused,muted:v.muted,volume:v.volume,tracks:[...v.audioTracks||[]].length}})())")
        state = json.loads(state) if state else None
        if state and state["ready"] >= 2 and 59.9 <= state["duration"] <= 60.1:
            break
        time.sleep(.2)
    else:
        raise RuntimeError(f"trailer video not ready: {state}")
    if (state["width"], state["height"]) != (1280, 720):
        raise RuntimeError(f"wrong trailer dimensions: {state}")
    if state["paused"] or state["muted"] or state["volume"] <= 0:
        raise RuntimeError(f"audio did not start on user click: {state}")
    click(".trailer-controls button[aria-pressed]")
    if not evaluate("document.querySelector('.trailer-dialog video').muted"):
        raise RuntimeError("mute did not work")
    click(".trailer-controls button[aria-pressed]")
    if evaluate("document.querySelector('.trailer-dialog video').muted"):
        raise RuntimeError("unmute did not work")
    evaluate("document.querySelectorAll('.trailer-dialog nav button')[4].click()")
    time.sleep(.6)
    position = evaluate("document.querySelector('.trailer-dialog video').currentTime")
    if not 40 <= position < 43:
        raise RuntimeError(f"clinic chapter seek failed: {position}")
    image = call("Page.captureScreenshot", {"format": "png"})["data"]
    (OUT / "trailer-player-clinic-60s.png").write_bytes(base64.b64decode(image))
    call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844,
                                                "deviceScaleFactor": 1, "mobile": True})
    call("Page.navigate", {"url": "http://127.0.0.1:4177/"})
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not evaluate("Boolean(document.querySelector('.trailer-preview button'))"):
        time.sleep(.2)
    click(".trailer-preview button")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not evaluate("Boolean(document.querySelector('.trailer-dialog video')?.readyState >= 2)"):
        time.sleep(.2)
    mobile = json.loads(evaluate("JSON.stringify((()=>{const v=document.querySelector('.trailer-dialog video');const d=document.querySelector('.trailer-dialog');return {playing:!v.paused,muted:v.muted,dialogWidth:d.getBoundingClientRect().width,viewport:innerWidth}})())"))
    if not mobile["playing"] or mobile["muted"] or mobile["dialogWidth"] > mobile["viewport"]:
        raise RuntimeError(f"mobile trailer failed: {mobile}")
    click(".trailer-controls button[aria-pressed]")
    if not evaluate("document.querySelector('.trailer-dialog video').muted"):
        raise RuntimeError("mobile mute failed")
    image = call("Page.captureScreenshot", {"format": "png"})["data"]
    (OUT / "trailer-player-mobile-390-music.png").write_bytes(base64.b64decode(image))
    print(f"PASS: desktop/mobile video {state['width']}x{state['height']} / {state['duration']} s, sound on user click, mute/unmute; clinic seek {position:.1f} s")
finally:
    call("Emulation.clearDeviceMetricsOverride")
    ws.close()
