"""Layout smoke at 360, 390 and 768 CSS pixels; simulation QA uses synthetic API."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path(__file__).resolve().parent / 'evidence'
page = next(item for item in requests.get('http://127.0.0.1:9225/json/list', timeout=5).json()
            if item.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
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


def evaluate(expression):
    return call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result'].get('value')


def ready(expression, label):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if evaluate(expression):
            return
        time.sleep(.2)
    raise RuntimeError(label)


def save(name):
    data = call('Page.captureScreenshot', {'format': 'png'})['data']
    (OUT / name).write_bytes(base64.b64decode(data))


def no_page_overflow(label):
    measurements = evaluate('({viewport:innerWidth,scroll:document.documentElement.scrollWidth})')
    if measurements['scroll'] > measurements['viewport'] + 2:
        raise RuntimeError(f'{label}: horizontal overflow {measurements}')


try:
    call('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 1})
    for width in (360, 390, 768):
        call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 800,
                                                   'deviceScaleFactor': 1, 'mobile': True})
        call('Page.navigate', {'url': 'http://127.0.0.1:4174/'})
        ready("Boolean(document.querySelector('#build-catalog button'))", 'RobCraft launcher')
        no_page_overflow(f'RobCraft {width} launcher')
        save(f'mobile-{width}-robcraft-launcher.png')
        evaluate("document.querySelector('#initial-view').value='2d'; document.querySelector('#world-form button[type=submit]').click()")
        ready("document.body.classList.contains('editor-active')", 'RobCraft construction')
        no_page_overflow(f'RobCraft {width} construction')
        save(f'mobile-{width}-robcraft-build.png')
        call('Page.navigate', {'url': 'http://127.0.0.1:4175/qa/recovery/index.html?kind=warehouse'})
        ready("document.querySelector('[data-glb-status]')?.dataset.glbStatus==='READY'", 'scene preview')
        no_page_overflow(f'scene {width}')
        save(f'mobile-{width}-scene-3d.png')
        evaluate("document.querySelector('.scene-preview-mobile-switch button:last-child').click()")
        ready("document.querySelector('.scene-preview-grid')?.dataset.mobileView==='2d'", 'scene 2D switch')
        save(f'mobile-{width}-scene-2d.png')
        call('Page.navigate', {'url': 'http://127.0.0.1:4175/'})
        ready("Boolean(document.querySelector('#root h1'))", 'main application')
        no_page_overflow(f'main {width}')
        save(f'mobile-{width}-home.png')
        print(width, 'PASS: home, RobCraft and scene, no page overflow, 2D switch')
finally:
    call('Emulation.clearDeviceMetricsOverride')
    call('Emulation.setTouchEmulationEnabled', {'enabled': False})
    ws.close()
