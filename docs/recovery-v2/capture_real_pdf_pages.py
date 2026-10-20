"""Render every locally catalog-backed PDF page in Chromium's PDF viewer."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket
from PIL import Image, ImageDraw
from pypdf import PdfReader

OUT = Path(__file__).resolve().parent / "evidence"
page = next(item for item in requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
            if item.get("type") == "page" and any(port in item.get("url", "") for port in (":4177/", ":4176/")))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
seq = 0


def call(method, params=None):
    global seq
    seq += 1
    key = seq
    ws.send(json.dumps({"id": key, "method": method, "params": params or {}}))
    while True:
        item = json.loads(ws.recv())
        if item.get("id") == key:
            if "error" in item:
                raise RuntimeError(item["error"])
            return item.get("result", {})


try:
    call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900,
                                               "deviceScaleFactor": 1, "mobile": False})
    for kind in ("warehouse", "airport", "clinic"):
        pdf = OUT / f"local-catalog-{kind}.pdf"
        count = len(PdfReader(pdf).pages)
        call("Page.navigate", {"url": f"http://127.0.0.1:4176/docs/recovery-v2/evidence/{pdf.name}"})
        time.sleep(2.0)
        thumbs = []
        for number in range(1, count + 1):
            call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 633, "y": 20,
                                              "button": "left", "clickCount": 1})
            call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 633, "y": 20,
                                              "button": "left", "clickCount": 1})
            call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2})
            call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2})
            call("Input.insertText", {"text": str(number)})
            call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            time.sleep(.8)
            target = OUT / f"local-catalog-{kind}-page{number}.png"
            target.write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
            thumb = Image.open(target).convert("RGB")
            thumb.thumbnail((320, 225))
            thumbs.append(thumb.copy())
        sheet = Image.new("RGB", (990, ((count + 2) // 3) * 255), "#d9dee0")
        draw = ImageDraw.Draw(sheet)
        for i, thumb in enumerate(thumbs):
            x, y = i % 3 * 330, i // 3 * 255
            sheet.paste(thumb, (x, y + 20))
            draw.text((x + 8, y + 4), f"{kind} · {i + 1}", fill="#25323a")
        sheet.save(OUT / f"local-catalog-{kind}-contact.png")
        print(kind, count, "pages", flush=True)
finally:
    call("Emulation.clearDeviceMetricsOverride")
    ws.close()
