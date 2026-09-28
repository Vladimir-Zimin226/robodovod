"""Read-only Chrome check: guest PDF, one player per result, navigation teardown.

Requires local Vite; API fixtures are immutable backup data served in memory.
No backend connection or database writes. All outputs are new files in .tmp.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

import websocket

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

ENTRY = r'''import React from 'react';
import {createRoot} from 'react-dom/client';
import App from '/src/App.jsx';
import '/src/index.css';
const data=await (await fetch('./cases.json')).json();
const selected=new URLSearchParams(location.search).get('case')||'airport';
const {run,request,report}=data[selected];
const project={id:request.project_id,name:'Проверка сохранённого результата',profile:{timezone:'Asia/Sakhalin'},scenarios:[]};
const nativeFetch=window.fetch.bind(window);
window.__errors=[];window.__api=[];
window.addEventListener('error',e=>window.__errors.push(e.error?.stack||e.message));
window.addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));
window.fetch=async (input,options={})=>{
 const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;
 if(!path.startsWith('/api/'))return nativeFetch(input,options);
 window.__api.push(path);
 if(options.method && options.method!=='GET')throw new Error('Check forbids API writes: '+path);
 let value={};
 if(path==='/api/auth/me')value={user:{id:'test',email:'test@example.test',role:'ADMIN'}};
 else if(path==='/api/projects')value={items:[project]};
 else if(path.includes('/candidate-comparisons/'))value={items:[],source_position_id:null};
 else if(path.endsWith('/evidence'))value={items:[{request,report}]};
 else if(path.endsWith('/analysis-runs'))value={items:[run]};
 else if(path.includes('/analysis-runs/'))value=run;
 else if(path==='/api/projects/'+project.id)value=project;
 return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
};
createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:5189')
    args = parser.parse_args()
    backup = ROOT / 'backup'
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in backup.rglob('*') if p.is_file()}
    rows = {r['id']: r for r in map(json.loads, (backup / 'database/analysis_runs.jsonl').read_text('utf-8').splitlines())}
    artifacts = [json.loads(line) for line in (backup / 'database/simulation_artifacts.jsonl').read_text('utf-8').splitlines()]
    cases = {}
    for template in ('warehouse', 'airport', 'hospital'):
        saved = max((a for a in artifacts if a['request_snapshot']['scenario_spec']['template'] == template), key=lambda a: a['created_at'])
        cases[template] = {'run': rows[saved['analysis_run_id']], 'request': saved['request_snapshot'], 'report': saved['report_snapshot']}
    harness = ROOT / 'frontend/.tmp-demo-review'
    harness.mkdir(exist_ok=True)
    output = ROOT / '.tmp/demo-simulation-review'
    output.mkdir(parents=True, exist_ok=True)
    profile = output / ('chrome-' + str(time.time_ns()))
    downloads = output / ('downloads-' + str(time.time_ns()))
    downloads.mkdir(exist_ok=True)
    (harness / 'index.html').write_text('<div id="root"></div><script type="module" src="./entry.jsx"></script>', encoding='utf-8')
    (harness / 'entry.jsx').write_text(ENTRY, encoding='utf-8')
    (harness / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
    chrome = subprocess.Popen([str(CHROME), '--headless=new', '--no-first-run', '--no-default-browser-check',
                               '--remote-allow-origins=*', '--remote-debugging-port=0', f'--user-data-dir={profile}', 'about:blank'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    seq = 0

    def call(method, params=None):
        nonlocal seq
        seq += 1
        ws.send(json.dumps({'id': seq, 'method': method, 'params': params or {}}))
        while True:
            response = json.loads(ws.recv())
            if response.get('id') == seq:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response.get('result', {})

    def js(code):
        result = call('Runtime.evaluate', {'expression': code, 'returnByValue': True, 'awaitPromise': True})
        if result.get('exceptionDetails'):
            raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    def until(code):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            value = js(code)
            if value:
                return value
            assert not js('window.__errors || []'), js('window.__errors')
            time.sleep(.1)
        raise AssertionError('Timeout: ' + code + '; ' + str(js('document.body.innerText.slice(-1000)')))

    def nav(text):
        js("[...document.querySelectorAll('.app-sidebar button')].find(b=>b.textContent.trim()===" + json.dumps(text) + ").click()")

    try:
        for _ in range(150):
            if (profile / 'DevToolsActivePort').exists():
                break
            time.sleep(.1)
        port = (profile / 'DevToolsActivePort').read_text().splitlines()[0]
        pages = json.load(urlopen(f'http://127.0.0.1:{port}/json/list'))
        ws = websocket.create_connection(next(p['webSocketDebuggerUrl'] for p in pages if p['type'] == 'page'), timeout=10)
        call('Page.enable')
        call('Runtime.enable')
        call('Emulation.setDeviceMetricsOverride', {'width': 1366, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
        call('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(downloads)})
        results = []
        for template in cases:
            call('Page.navigate', {'url': f'{args.url}/{harness.name}/index.html?case={template}#reports'})
            until("document.querySelectorAll('.reports-card').length===1")
            js("[...document.querySelectorAll('.reports-card button')].find(b=>b.textContent==='Открыть').click()")
            until("document.querySelector('.simulation-2d svg')!==null")
            assert js("document.querySelectorAll('.simulation-2d').length") == 1
            assert not js("document.body.innerText.includes('Открыть другую сохранённую симуляцию')")
            assert not js("document.querySelector('[aria-label=\"Физический сценарий проекта\"]')")
            # Open an iframe, then verify it and the entire player disappear on navigation.
            js("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='3D').click()")
            until("document.querySelector('iframe')!==null")
            for label in ('Главная', 'Расчёт', 'Библиотека решений'):
                nav(label)
                until("document.querySelector('.simulation-2d')===null && document.querySelector('iframe')===null")
            assert not js('window.__errors'), js('window.__errors')
            results.append({'template': template, 'single_player': True, 'project_switcher_removed': True, 'navigation_teardown': True, 'result_schema': cases[template]['run']['result_snapshot']['schema_version']})
        call('Page.navigate', {'url': f'{args.url}/{harness.name}/index.html#demo-warehouse'})
        until("document.querySelector('a[download=\"warehouse-pallet-investor-full-v1.pdf\"]')!==null")
        assert js("document.querySelectorAll('.simulation-2d').length") == 1
        js("document.querySelector('a[download=\"warehouse-pallet-investor-full-v1.pdf\"]').click()")
        target = downloads / 'warehouse-pallet-investor-full-v1.pdf'
        deadline = time.monotonic() + 20
        while not target.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        assert target.read_bytes() == (ROOT / 'frontend/public/demo/warehouse-pallet-investor-v1/report.pdf').read_bytes()
        results.append({'guest_pdf_download_matches': True, 'bytes': target.stat().st_size, 'single_player': True})
        data = call('Page.captureScreenshot', {'format': 'png'})['data']
        (output / 'guest-screen.png').write_bytes(base64.b64decode(data))
        (output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(results, ensure_ascii=False), flush=True)
    finally:
        if ws:
            ws.close()
        subprocess.run(['taskkill', '/PID', str(chrome.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        chrome.wait(timeout=5)
        for name in ('index.html', 'entry.jsx', 'cases.json'):
            (harness / name).unlink(missing_ok=True)
        harness.rmdir()
        assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}, 'backup changed'


if __name__ == '__main__':
    main()
