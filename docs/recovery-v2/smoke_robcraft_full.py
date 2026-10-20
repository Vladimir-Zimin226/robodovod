"""Run the complete local RobCraft construction path through the browser UI."""

import base64
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
import websocket

OUT = Path(__file__).resolve().parent / 'evidence'
page = next(item for item in requests.get('http://127.0.0.1:9225/json/list', timeout=5).json()
            if item.get('type') == 'page')
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
serial = 0
WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 1440


def call(method, params=None):
    global serial
    serial += 1
    current = serial
    ws.send(json.dumps({'id': current, 'method': method, 'params': params or {}}))
    while True:
        result = json.loads(ws.recv())
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
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if evaluate(expression):
            return
        time.sleep(.15)
    raise RuntimeError(f'{label}: {evaluate("document.querySelector(\'#editor-message\')?.textContent")}')


def save(name):
    (OUT / name).write_bytes(capture())


def capture():
    data = call('Page.captureScreenshot', {'format': 'png'})['data']
    return base64.b64decode(data)


def map_click(x, z):
    point = json.loads(evaluate(f"JSON.stringify((()=>{{const r=document.querySelector('#craft-map').getBoundingClientRect();"
                                f"const scale=Math.min(r.width/56,r.height/46);return [r.left+r.width/2+({x})*scale,"
                                f"r.top+r.height/2+({z})*scale]}})())"))
    call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': point[0], 'y': point[1], 'button': 'left', 'clickCount': 1})
    call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': point[0], 'y': point[1], 'button': 'left', 'clickCount': 1})
    time.sleep(.15)


def catalog(kind, category):
    evaluate("document.querySelector('#inventory-toggle').click()") if evaluate("document.querySelector('#editor-panel').classList.contains('hidden')") else None
    evaluate(f"[...document.querySelectorAll('.catalog-tabs button')].find(x=>x.textContent==={json.dumps(category)}).click()")
    if evaluate(f"document.querySelector('[data-kind={kind}]').classList.contains('hidden')"):
        raise RuntimeError(f'{kind} catalog item hidden')
    evaluate(f"document.querySelector('[data-kind={kind}]').click()")
    if WIDTH <= 760:
        evaluate("document.querySelector('#inventory-toggle').click()")


def current_document(seed):
    payload = evaluate(f"JSON.stringify((()=>{{const key=Object.keys(localStorage).find(x=>x.startsWith('robcraft:scene:v1:warehouse:')&&x.includes({json.dumps(seed)}));return key?JSON.parse(localStorage.getItem(key)).document:null}})())")
    if not payload:
        raise RuntimeError(f"scene not saved; keys={evaluate('JSON.stringify(Object.keys(localStorage))')}")
    return json.loads(payload)


try:
    call('Network.setCacheDisabled', {'cacheDisabled': True})
    call('Emulation.setDeviceMetricsOverride', {'width': WIDTH, 'height': 800 if WIDTH <= 760 else 900,
                                                'deviceScaleFactor': 1, 'mobile': WIDTH <= 760})
    if WIDTH <= 760:
        call('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 1})
    token = str(int(time.time() * 1000))
    call('Page.navigate', {'url': 'about:blank'})
    until("location.href==='about:blank' && document.readyState==='complete'", 'blank document')
    call('Page.navigate', {'url': f'http://127.0.0.1:4174/?smoke={token}'})
    until(f"location.search.includes('smoke={token}') && document.readyState==='complete' && Boolean(document.querySelector('#build-catalog button'))", 'RobCraft launcher')
    assert not evaluate("Boolean(document.querySelector('#world-description'))")
    seed = f'R2-E2E-{int(time.time())}'
    evaluate(f"document.querySelector('#seed').value={json.dumps(seed)};document.querySelector('#initial-view').value='2d';document.querySelector('[data-start=empty]').click();document.querySelector('#world-form button[type=submit]').click()")
    until("document.body.classList.contains('editor-active') && !document.querySelector('#craft-map').classList.contains('hidden')", '2D editor')
    catalog('rack', 'Конструкции')
    for x in (-10, -5, 0):
        map_click(x, -7)
    document = current_document(seed)
    assert sum(item['kind'] == 'rack' for item in document['scenePatch']['created']) == 3
    evaluate("document.querySelector('#empty-hand').click()")
    map_click(-5, -7)
    document = current_document(seed)
    assert sum(item['kind'] == 'rack' for item in document['scenePatch']['created']) == 2
    catalog('charging_dock', 'Зоны/Маршруты'); map_click(-11, 7)
    catalog('station', 'Мебель/Оборудование'); map_click(0, 7)
    catalog('pallet_stack', 'Мебель/Оборудование'); map_click(10, 7)
    catalog('pallet_amr', 'Роботы'); map_click(-10, 1)
    document = current_document(seed)
    assert len(document['scenePatch']['created']) == 6
    assert {item.get('operational_role') for item in document['scenePatch']['created']} >= {'CHARGE', 'WORK', 'DROPOFF'}
    evaluate("document.querySelector('#craft-play').click()")
    until("Boolean(document.querySelector('#operational-assignment-list').children.length)", 'robot assignment')
    assert evaluate("document.querySelector('#craft-play').getAttribute('aria-pressed')") == 'true'
    start = evaluate("document.querySelector('#operational-live-status').textContent")
    with tempfile.TemporaryDirectory(prefix='robcraft-motion-') as tmp:
        frames = Path(tmp)
        next_frame = time.monotonic()
        for index in range(24):
            (frames / f'frame-{index:03d}.png').write_bytes(capture())
            next_frame += .125
            if next_frame > time.monotonic():
                time.sleep(next_frame-time.monotonic())
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '8',
                        '-i', str(frames / 'frame-%03d.png'), '-c:v', 'libx264', '-preset', 'veryfast',
                        '-crf', '28', '-pix_fmt', 'yuv420p', str(OUT / f'robcraft-motion-{WIDTH}.mp4')], check=True)
    end = evaluate("document.querySelector('#operational-live-status').textContent")
    assert start != end and 'В движении' in end, (start, end)
    evaluate("document.querySelector('#craft-play').click()")
    until("document.querySelector('#operational-live-status').textContent.includes('Пауза')", 'robot pause')
    assert 'Роботы: 1/1' in evaluate("document.querySelector('#craft-economics-summary').textContent")
    save(f'robcraft-play-{WIDTH}.png')
    evaluate("document.querySelector('#craft-economics-summary').click()")
    economics = evaluate("document.querySelector('#economics-result').textContent")
    assert 'Статус:' in economics and 'CAPEX' in economics and 'NPV' in economics
    save(f'robcraft-full-{WIDTH}.png')
    # Explicit browser test inputs; these values are not catalog prices or an investment claim.
    fixture = {'staff_count': 3, 'monthly_employer_cost': 50000, 'workdays_year': 250,
               'hours_shift': 8, 'human_tasks_shift': 100, 'task_share': 1,
               'workload_day': 50, 'realization_share': .5, 'robot_price': 1000000,
               'integration_cost': 0, 'annual_service': 100000, 'annual_energy': 20000,
               'discount_rate': .1, 'operation_seconds': 30}
    evaluate(f"(()=>{{const fixture={json.dumps(fixture)};for(const input of document.querySelectorAll('[data-economics-field]')) input.value=fixture[input.dataset.economicsField];document.querySelector('#economics-apply').click()}})()")
    summary = evaluate("document.querySelector('#craft-economics-summary').textContent")
    assert '1 000 000' in summary.replace('\u00a0', ' ') and 'нужны вводные' not in summary, summary
    save(f'robcraft-economics-fixture-{WIDTH}.png')
    call('Page.reload', {'ignoreCache': True})
    time.sleep(1.2)
    until("document.readyState==='complete' && Boolean(document.querySelector('[data-start=mine]')) && !document.body.classList.contains('editor-active')", 'launcher after reload')
    evaluate("document.querySelector('[data-start=mine]').click();document.querySelector('#world-form button[type=submit]').click()")
    until("document.body.classList.contains('editor-active')", 'saved scene reopen')
    assert len(current_document(seed)['scenePatch']['created']) == 6
    assert current_document(seed)['scenePatch']['economics']['robot_price'] == 1000000
    print('PASS: catalog, place×3, break×1, roles, robot, path, Play, economy, save/reopen', flush=True)
finally:
    call('Emulation.clearDeviceMetricsOverride')
    if WIDTH <= 760:
        call('Emulation.setTouchEmulationEnabled', {'enabled': False})
    ws.close()
