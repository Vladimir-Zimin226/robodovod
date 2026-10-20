"""Browser playback against local FastAPI route-preview, without a mocked POST response."""

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
serial = 0
responses = []


def call(method, params=None):
    global serial
    serial += 1
    current = serial
    ws.send(json.dumps({'id': current, 'method': method, 'params': params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get('method') == 'Network.responseReceived':
            response = result['params']['response']
            if '/api/v2/' in response['url']:
                responses.append({'path': response['url'].split('/api/v2/', 1)[1],
                                  'status': response['status']})
        if result.get('id') == current:
            if 'error' in result:
                raise RuntimeError(result['error'])
            return result.get('result', {})


def evaluate(expression):
    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result']
    if result.get('exceptionDetails'):
        raise RuntimeError(result['exceptionDetails'])
    return result.get('value')


def until(expression, label):
    deadline = time.monotonic()+20
    while time.monotonic() < deadline:
        if evaluate(expression):
            return
        time.sleep(.2)
    raise RuntimeError(f'{label}: {evaluate("document.querySelector(\'.scene-sim-error\')?.textContent")}')


def save(name):
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
    call('Page.navigate', {'url': 'http://127.0.0.1:4175/qa/recovery/index.html?kind=warehouse&api=real'})
    until("location.search.includes('api=real') && document.querySelector('[data-glb-status]')?.dataset.glbStatus==='READY' && Boolean(document.querySelector('.scene-sim-controls button[type=submit]'))", 'real scene ready')
    assert 'локального FastAPI' in evaluate("document.querySelector('main p').textContent")
    evaluate("document.querySelector('.scene-sim-controls button[type=submit]').click()")
    until("Boolean(document.querySelector('.scene-playback-controls'))", 'backend playback')
    first = evaluate("document.querySelector('#recovery-pose').textContent")
    save('real-route-warehouse-start.png')
    time.sleep(4)
    second = evaluate("document.querySelector('#recovery-pose').textContent")
    save('real-route-warehouse-after-4s.png')
    if first == second:
        raise RuntimeError(f'robot did not move: {first}')
    evaluate("document.querySelector('.scene-playback-controls button').click()")
    paused = evaluate("document.querySelector('#recovery-pose').textContent")
    time.sleep(.5)
    assert paused == evaluate("document.querySelector('#recovery-pose').textContent"), 'pause changed pose'
    evaluate("document.querySelectorAll('.scene-sim-controls details')[1].open=true")
    for label, value in [('Препятствие: центр X', 11), ('Препятствие: центр Y', 34),
                         ('Препятствие: ширина', 3), ('Препятствие: длина', 3)]:
        fill_field(label, value)
    evaluate("document.querySelector('.scene-sim-controls button[type=submit]').click()")
    until("document.querySelector('.scene-preview-evidence')?.textContent.includes('NO_ROUTE')", 'blocked route')
    until("document.querySelector('[data-glb-status]')?.dataset.glbStatus==='READY'", 'blocked scene GLB reload')
    assert not evaluate("Boolean(document.querySelector('.scene-playback-controls'))"), 'blocked route still playing'
    save('real-route-warehouse-blocked.png')
    if not any(row['path'] == 'warehouse-roles/route-preview' and row['status'] == 200 for row in responses):
        raise RuntimeError(f'no successful real route-preview response: {responses}')
    (OUT / 'real-route-warehouse-network.json').write_text(json.dumps(responses, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PASS: real FastAPI route-preview; {first} -> {second}; pause holds; obstacle blocks route; {responses}')
finally:
    call('Emulation.clearDeviceMetricsOverride')
    ws.close()
