"""Capture the first page of the local fixture PDF through Chromium's PDF viewer."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent / 'evidence'
page = next(item for item in requests.get('http://127.0.0.1:9225/json/list', timeout=5).json()
            if item.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=15, suppress_origin=True)
index = 0


def call(method, params=None):
    global index
    index += 1
    current = index
    ws.send(json.dumps({'id': current, 'method': method, 'params': params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get('id') == current:
            if 'error' in result:
                raise RuntimeError(result['error'])
            return result.get('result', {})


try:
    call('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
    for kind in ('warehouse', 'airport', 'clinic'):
        target = ROOT / f'pdf-layout-fixture-{kind}.pdf'
        thumbnails = []
        call('Page.navigate', {'url': f'http://127.0.0.1:4176/docs/recovery-v2/evidence/{target.name}'})
        time.sleep(1.5)
        for number in range(1, len(PdfReader(target).pages) + 1):
            call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': 633, 'y': 20, 'button': 'left', 'clickCount': 1})
            call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': 633, 'y': 20, 'button': 'left', 'clickCount': 1})
            call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'a', 'code': 'KeyA', 'modifiers': 2})
            call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'a', 'code': 'KeyA', 'modifiers': 2})
            call('Input.insertText', {'text': str(number)})
            call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
            call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
            time.sleep(.35)
            data = call('Page.captureScreenshot', {'format': 'png'})['data']
            screenshot = ROOT / f'pdf-layout-fixture-{kind}-page{number}.png'
            screenshot.write_bytes(base64.b64decode(data))
            image = Image.open(screenshot).convert('RGB')
            image.thumbnail((320, 225))
            thumbnails.append(image.copy())
        columns = 3
        rows = (len(thumbnails) + columns - 1) // columns
        sheet = Image.new('RGB', (columns * 330, rows * 255), '#d9dee0')
        draw = ImageDraw.Draw(sheet)
        for offset, image in enumerate(thumbnails):
            x, y = offset % columns * 330, offset // columns * 255
            sheet.paste(image, (x, y + 20))
            draw.text((x + 8, y + 4), f'{kind} · {offset + 1}', fill='#25323a')
        sheet.save(ROOT / f'pdf-layout-fixture-{kind}-contact.png')
        print(kind, len(thumbnails), 'pages')
finally:
    call('Emulation.clearDeviceMetricsOverride')
    ws.close()
