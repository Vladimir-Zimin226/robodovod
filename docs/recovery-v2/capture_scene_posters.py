"""Capture true WebGL canvas pixels for illustrative landing cards, not simulation proof."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path(__file__).resolve().parents[2] / 'frontend' / 'public' / 'demo' / 'scenes'
OUT.mkdir(parents=True, exist_ok=True)
page = next(item for item in requests.get('http://127.0.0.1:9225/json/list', timeout=5).json()
            if item.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
number = 0


def call(method, params=None):
    global number
    number += 1
    current = number
    ws.send(json.dumps({'id': current, 'method': method, 'params': params or {}}))
    while True:
        message = json.loads(ws.recv())
        if message.get('id') == current:
            if 'error' in message:
                raise RuntimeError(message['error'])
            return message.get('result', {})


def evaluate(expression):
    return call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result'].get('value')


try:
    call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
    for kind in ('warehouse', 'airport', 'clinic'):
        call('Page.navigate', {'url': f'http://127.0.0.1:4175/qa/recovery/index.html?kind={kind}'})
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if evaluate("document.querySelector('[data-glb-status]')?.dataset.glbStatus") == 'READY':
                break
            time.sleep(.2)
        else:
            raise RuntimeError(f'{kind}: GLB unavailable')
        url = evaluate("document.querySelector('.scene-preview-canvas').toDataURL('image/png')")
        (OUT / f'{kind}.png').write_bytes(base64.b64decode(url.split(',', 1)[1]))
        print(kind, (OUT / f'{kind}.png').stat().st_size)
finally:
    call('Emulation.clearDeviceMetricsOverride')
    ws.close()
