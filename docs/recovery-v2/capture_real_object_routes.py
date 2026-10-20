"""Browser proof of airport and clinic route geometry from local FastAPI, no API mock."""

import base64
import json
import sys
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'evidence'
pages = requests.get('http://127.0.0.1:9225/json/list', timeout=5).json()
page = next((item for item in pages if item.get('type') == 'page'
             and '/qa/recovery/index.html' in item.get('url', '')),
            next(item for item in pages if item.get('type') == 'page'))
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=20,
                                 suppress_origin=True)
serial = 0
responses = []


def call(method, params=None):
    global serial
    serial += 1
    request_id = serial
    ws.send(json.dumps({'id': request_id, 'method': method, 'params': params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get('method') == 'Network.responseReceived':
            response = result['params']['response']
            if '/api/v2/' in response['url']:
                responses.append({'path': response['url'].split('/api/v2/', 1)[1],
                                  'status': response['status']})
        if result.get('id') == request_id:
            if 'error' in result:
                raise RuntimeError(result['error'])
            return result.get('result', {})


def evaluate(expression):
    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result']
    if result.get('exceptionDetails'):
        raise RuntimeError(result['exceptionDetails'])
    return result.get('value')


def until(expression, label):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if evaluate(expression):
            return
        time.sleep(.2)
    raise RuntimeError(f'{label}: {evaluate("document.body.innerText.slice(0,700)")}')


def save(name):
    evaluate("document.querySelector('.scene-preview')?.scrollIntoView({block:'center'})")
    time.sleep(.2)
    data = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})['data']
    (OUT / name).write_bytes(base64.b64decode(data))


def fill_field(label, value):
    expression = f"(()=>{{const input=[...document.querySelectorAll('.scene-sim-controls label')].find(x=>x.textContent.trim().startsWith({json.dumps(label)}))?.querySelector('input');if(!input)throw Error('missing field');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,{json.dumps(str(value))});input.dispatchEvent(new Event('input',{{bubbles:true}}))}})()"
    evaluate(expression)


try:
    call('Network.enable')
    call('Network.setCacheDisabled', {'cacheDisabled': True})
    call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900,
                                                'deviceScaleFactor': 1, 'mobile': False})
    for kind in (sys.argv[1:] or ('airport', 'clinic')):
        start_index = len(responses)
        call('Page.navigate', {'url': f'http://127.0.0.1:4175/qa/recovery/index.html?kind={kind}&api=real'})
        until("document.querySelector('[data-glb-status]')?.dataset.glbStatus==='READY' && Boolean(document.querySelector('.scene-sim-controls button[type=submit]'))", f'{kind} ready')
        assert 'локального FastAPI' in evaluate("document.querySelector('main p').textContent")
        evaluate("document.querySelector('.scene-sim-controls button[type=submit]').click()")
        until("Boolean(document.querySelector('.scene-playback-controls'))", f'{kind} playback')
        first = evaluate("document.querySelector('#recovery-pose').textContent")
        save(f'real-route-{kind}-start.png')
        time.sleep(3)
        second = evaluate("document.querySelector('#recovery-pose').textContent")
        save(f'real-route-{kind}-after-3s.png')
        assert first != second, f'{kind}: robot did not move'
        evaluate("document.querySelector('.scene-playback-controls button').click()")
        paused = evaluate("document.querySelector('#recovery-pose').textContent")
        time.sleep(.5)
        assert paused == evaluate("document.querySelector('#recovery-pose').textContent"), f'{kind}: pause changed pose'
        if kind == 'airport':
            assert evaluate("document.querySelector('.scene-sim-controls')?.textContent.includes('Для показа маршрута использован поток')"), 'sampling disclosure missing'
        scene = json.loads((ROOT / 'data/scenes' / f'{kind}.scene.json').read_text(encoding='utf-8'))
        pickup = next(zone['center_xy_m'] for zone in scene['zones'] if zone['zone_id'] == 'pickup')
        evaluate("document.querySelectorAll('.scene-sim-controls details')[1].open=true")
        for label, value in [('Препятствие: центр X', pickup[0]), ('Препятствие: центр Y', pickup[1]),
                             ('Препятствие: ширина', 3), ('Препятствие: длина', 3)]:
            fill_field(label, value)
        evaluate("document.querySelector('.scene-sim-controls button[type=submit]').click()")
        until("document.querySelector('.scene-preview-evidence')?.textContent.includes('NO_ROUTE')", f'{kind} blocked')
        assert not evaluate("Boolean(document.querySelector('.scene-playback-controls'))"), f'{kind}: blocked route playing'
        save(f'real-route-{kind}-blocked.png')
        trace = responses[start_index:]
        assert any(row['path'] == f'object-roles/{kind.upper()}/route-preview' and row['status'] == 200
                   for row in trace), f'{kind}: no backend response {trace}'
        (OUT / f'real-route-{kind}-network.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
        print(f'{kind}: PASS {first} -> {second}; pause, NO_ROUTE, {trace}')
finally:
    call('Emulation.clearDeviceMetricsOverride')
    ws.close()
