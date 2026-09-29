"""Read-only playback of the latest saved 15-robot warehouse artifact in local Chrome."""
import json
import re
import shutil
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from local_browser import LocalBrowser, ROOT

OUT = ROOT / '.test-warehouse-activity/browser'
HARNESS = ROOT / 'frontend/.test-warehouse-activity'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    artifacts = [json.loads(line) for line in (ROOT / 'backup/database/simulation_artifacts.jsonl').read_text(encoding='utf-8').splitlines()]
    warehouse = [row for row in artifacts if row['request_snapshot']['scenario_spec']['template'] == 'warehouse'
                 and sum(fleet['selected_fleet'] for fleet in row['request_snapshot']['scenario_spec']['fleet']) == 15]
    assert warehouse, 'The diagnostic backup has no saved 15-robot warehouse artifact'
    artifact = max(warehouse, key=lambda row: row['created_at'])
    HARNESS.mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = {'request': artifact['request_snapshot'], 'report': artifact['report_snapshot']}
    (HARNESS / 'fixture.json').write_text(json.dumps(fixture, ensure_ascii=False), encoding='utf-8')
    (HARNESS / 'index.html').write_text('''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body><div id="root"></div><script type="module">
import React from 'react';import{createRoot}from'react-dom/client';import Simulation from '/src/components/Simulation2DReport.jsx';import '/src/index.css';
const saved=await(await fetch('./fixture.json')).json();window.messages=[];window.addEventListener('message',e=>{if(e.origin===location.origin)window.messages.push(e.data)});
createRoot(document.getElementById('root')).render(React.createElement(Simulation,{request:saved.request,initialReport:saved.report}));window.ready=true;
</script></body></html>''', encoding='utf-8')
    config = HARNESS / 'vite.config.mjs'
    dist = OUT / 'dist'
    config.write_text("import base from '../vite.config.js';export default {...base,plugins:base.plugins.filter(plugin=>plugin.name!=='robcraft-same-origin-assets'),build:{outDir:" + json.dumps(str(dist))
                      + ",emptyOutDir:true,rollupOptions:{input:" + json.dumps(str(HARNESS / 'index.html')) + "}}};", encoding='utf-8')
    built = subprocess.run(['node', '--preserve-symlinks', '--preserve-symlinks-main', 'node_modules/vite/bin/vite.js',
                            'build', '--configLoader', 'runner', '--config', str(config)], cwd=ROOT / 'frontend', capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    robcraft = dist / 'robcraft'
    robcraft.mkdir(exist_ok=True)
    for filename in ('index.html', 'styles.css'):
        shutil.copyfile(ROOT / 'robcraft' / filename, robcraft / filename)
    shutil.copytree(ROOT / 'robcraft/src', robcraft / 'src', dirs_exist_ok=True)
    shutil.copyfile(HARNESS / 'fixture.json', dist / '.test-warehouse-activity/fixture.json')
    server = ThreadingHTTPServer(('127.0.0.1', 5192), partial(QuietHandler, directory=str(dist)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    browser = LocalBrowser('http://127.0.0.1:5192/.test-warehouse-activity/index.html', OUT)
    evidence = {'artifact_id': artifact['id'], 'saved_created_at': artifact['created_at'], 'screens': []}

    def viewport(width, height):
        browser.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width < 800})

    def click(label):
        browser.js(f"[...document.querySelectorAll('button')].find(x=>x.textContent==={json.dumps(label)}).click()")

    try:
        browser.until('window.ready')
        browser.until("document.querySelector('.simulation-controls')?.dataset.playbackStatus==='RUNNING'", timeout=30)
        click('Пауза')
        browser.until("document.querySelector('.simulation-controls')?.dataset.playbackStatus==='PAUSED'")
        browser.js("(()=>{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'180');x.dispatchEvent(new Event('input',{bubbles:true}))})()")
        browser.until("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)===10800")
        for width, height in [(390, 844), (768, 1024), (1366, 900), (1920, 1080)]:
            viewport(width, height)
            result = browser.js("(()=>{const svg=document.querySelector('.facility-plan svg');return {svg_width:svg.getBoundingClientRect().width,racks:[...svg.querySelectorAll('g > title')].filter(x=>x.textContent.startsWith('Стеллаж')).length,robots:document.querySelectorAll('.facility-plan .facility-operations > div').length,overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth}})()")
            assert result['racks'] == result['robots'] == 15 and result['overflow'] <= 1, result
            browser.js("document.querySelector('.facility-plan svg').scrollIntoView({block:'center'})")
            browser.screenshot(f'warehouse-15-2d-{width}.png')
            evidence['screens'].append({'view': '2D', 'width': width, 'height': height, **result})
            samples = []
            for minute in (0, 15, 60, 180, 300):
                browser.js(f"(()=>{{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'{minute}');x.dispatchEvent(new Event('input',{{bubbles:true}}))}})()")
                browser.until(f"Number(document.querySelector('.simulation-controls').dataset.modelSeconds)==={minute * 60}")
                samples.append(browser.js("(()=>{const box=document.querySelector('.facility-plan .facility-operations');return {height:box.getBoundingClientRect().height,card_heights:[...box.children].filter(x=>x.tagName==='DIV').map(x=>x.getBoundingClientRect().height),status:box.innerText.slice(0,120)}})()"))
            assert len({sample['height'] for sample in samples}) == 1, (width, samples)
            assert all(len(set(sample['card_heights'])) == 1 for sample in samples), (width, samples)
            assert len({height for sample in samples for height in sample['card_heights']}) == 1, (width, samples)
            evidence['screens'].append({'view': '2D-card-stability', 'width': width, 'sample_minutes': [0, 15, 60, 180, 300], 'height': samples[0]['height'], 'card_height': samples[0]['card_heights'][0]})
        viewport(1366, 900)
        browser.js("(()=>{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'180');x.dispatchEvent(new Event('input',{bubbles:true}))})()")
        browser.until("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)===10800")
        click('3D')
        browser.until("window.messages.some(x=>x.type==='ROBCRAFT_REPORT'&&x.payload.versions.renderer_engine_version==='conditional-live-playback-v3')", timeout=30)
        browser.until("document.querySelector('iframe')?.contentDocument?.querySelector('#hud-robots')?.textContent==='15'", timeout=30)
        browser.until("document.querySelector('iframe')?.contentDocument?.querySelector('#hud-time')?.textContent==='12:00'", timeout=30)
        browser.js("document.querySelector('iframe').scrollIntoView({block:'center'})")
        browser.screenshot('warehouse-15-3d-overview.png')
        for width, height in [(390, 844), (768, 1024), (1366, 900), (1920, 1080)]:
            viewport(width, height)
            browser.js("(()=>{const gl=document.querySelector('iframe').contentDocument.querySelector('canvas').getContext('webgl');if(!gl.__originalClear){gl.__originalClear=gl.clear.bind(gl);gl.__originalDraw=gl.drawArrays.bind(gl);gl.clear=(...args)=>{gl.__visualFrames++;return gl.__originalClear(...args)};gl.drawArrays=(...args)=>{gl.__drawCalls++;return gl.__originalDraw(...args)}}gl.__visualFrames=0;gl.__drawCalls=0})()")
            sample = browser.js("new Promise(resolve=>{const start=performance.now();setTimeout(()=>{const gl=document.querySelector('iframe').contentDocument.querySelector('canvas').getContext('webgl');resolve({seconds:(performance.now()-start)/1000,frames:gl.__visualFrames,draw_calls:gl.__drawCalls})},3000)})")
            result = {'rendered_fps': sample['frames'] / sample['seconds'], 'draw_calls_per_frame': sample['draw_calls'] / max(1, sample['frames']),
                      'overflow': browser.js('document.documentElement.scrollWidth-document.documentElement.clientWidth'),
                      'panel_height': browser.js("document.querySelector('iframe').getBoundingClientRect().height")}
            assert result['rendered_fps'] >= 30 and result['overflow'] <= 1, (width, result)
            browser.js("document.querySelector('iframe').scrollIntoView({block:'center'})")
            browser.screenshot(f'warehouse-15-3d-{width}.png')
            evidence['screens'].append({'view': '3D', 'width': width, 'height': height, **result})
            samples = []
            for minute in (0, 15, 60, 180, 300):
                browser.js(f"(()=>{{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'{minute}');x.dispatchEvent(new Event('input',{{bubbles:true}}))}})()")
                browser.until(f"Number(document.querySelector('.simulation-controls').dataset.modelSeconds)==={minute * 60}")
                samples.append(browser.js("(()=>{const box=document.querySelector('[aria-label=\"Действия роботов в 3D\"]');return {height:box.getBoundingClientRect().height,card_heights:[...box.children].map(x=>x.getBoundingClientRect().height),status:box.innerText.slice(0,120)}})()"))
            assert len({sample['height'] for sample in samples}) == 1, (width, samples)
            assert all(len(set(sample['card_heights'])) == 1 for sample in samples), (width, samples)
            assert len({height for sample in samples for height in sample['card_heights']}) == 1, (width, samples)
            evidence['screens'].append({'view': '3D-card-stability', 'width': width, 'sample_minutes': [0, 15, 60, 180, 300], 'height': samples[0]['height'], 'card_height': samples[0]['card_heights'][0]})
        viewport(1366, 900)
        click('Старт')
        start_model = browser.js("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)")
        captions = browser.js("new Promise(resolve=>{const values=[];let n=0;const timer=setInterval(()=>{values.push(document.querySelector('iframe').contentDocument.querySelector('#director-caption').textContent);if(++n===34){clearInterval(timer);resolve(values)}},1000)})")
        end_model = browser.js("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)")
        click('Пауза')
        shots = [re.match(r'^Робот \d+', caption).group(0) if re.match(r'^Робот \d+', caption) else caption for caption in captions]
        changes = sum(a != b for a, b in zip(shots, shots[1:]))
        evidence['camera'] = {'tracked_robot_changes_in_34_seconds': changes, 'model_seconds_advanced': end_model - start_model,
                              'shots': shots}
        assert end_model - start_model > 1000 and changes <= 2 and all(shot.startswith('Робот ') for shot in shots), evidence['camera']
        button = browser.js("(()=>{const f=document.querySelector('iframe');const a=f.getBoundingClientRect();const b=f.contentDocument.querySelector('#manual-toggle').getBoundingClientRect();return {x:a.left+b.left+b.width/2,y:a.top+b.top+b.height/2}})()")
        browser.call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': button['x'], 'y': button['y'], 'button': 'left', 'clickCount': 1})
        browser.call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': button['x'], 'y': button['y'], 'button': 'left', 'clickCount': 1})
        browser.until("Boolean(document.querySelector('iframe').contentDocument.pointerLockElement)")
        browser.screenshot('warehouse-15-3d-manual.png')
        evidence['manual_camera'] = {'pointer_locked': True}
        print(json.dumps(evidence, ensure_ascii=False))
    finally:
        (OUT / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    sys.exit(main())
