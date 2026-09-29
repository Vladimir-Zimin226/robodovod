"""Local synthetic control/clock/3D/GPU acceptance. Requires local Vite :5189."""
import json
import subprocess
import time
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from local_browser import LocalBrowser, ROOT

OUT = ROOT / '.test-product-chain-implementation/session/playback-browser'
HARNESS = ROOT / 'frontend/.test-safe-playback'


def main():
    HARNESS.mkdir(exist_ok=True)
    bundle = subprocess.check_output(['node', '--preserve-symlinks', '--input-type=module', '-e',
        "import {playbackCase} from './robcraft/tests/support/safe-case.js';const cases=['warehouse','airport','hospital'].map(x=>playbackCase(x,x==='warehouse'?11:x==='airport'?6:4));console.log(JSON.stringify(cases));"],cwd=ROOT)
    (HARNESS / 'fixture.json').write_bytes(bundle)
    (HARNESS / 'index.html').write_text('''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body><div id="root"></div><script type="module">
import React from 'react';import{createRoot}from'react-dom/client';import Simulation from '/src/components/Simulation2DReport.jsx';import '/src/index.css';
const cases=await(await fetch('./fixture.json')).json();const root=createRoot(document.getElementById('root'));
window.messages=[];window.addEventListener('message',e=>{if(e.origin===location.origin)window.messages.push(e.data)});
window.show=i=>root.render(React.createElement(Simulation,{key:i,request:cases[i].request,initialReport:cases[i].report}));window.show(0);window.ready=true;
</script></body></html>''',encoding='utf-8')
    # Measure a compiled build, with no development hot reload interrupting the clocks.
    config=HARNESS/'vite.config.mjs'
    dist=OUT/'dist'
    config.write_text("import base from '../vite.config.js';export default {...base,build:{outDir:"+json.dumps(str(dist))+",emptyOutDir:true,rollupOptions:{input:"+json.dumps(str(HARNESS/'index.html'))+"}}};",encoding='utf-8')
    built=subprocess.run(['node','node_modules/vite/bin/vite.js','build','--config',str(config)],cwd=ROOT/'frontend',capture_output=True,text=True)
    assert built.returncode==0,built.stdout+built.stderr
    shutil.copyfile(HARNESS/'fixture.json',dist/'.test-safe-playback/fixture.json')
    server=ThreadingHTTPServer(('127.0.0.1',5191),partial(SimpleHTTPRequestHandler,directory=str(dist)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    browser = LocalBrowser('http://127.0.0.1:5191/.test-safe-playback/index.html', OUT, software_gpu=True)
    evidence={'gpu':'not inspected','checks':[]}
    def click(label):
        browser.js(f"[...document.querySelectorAll('button')].find(x=>x.textContent==={json.dumps(label)}).click()")
        status={'Старт':'RUNNING','Перезапуск':'RUNNING','Стоп':'STOPPED','Пауза':'PAUSED'}.get(label)
        if status:
            browser.until(f"document.querySelector('.simulation-controls')?.dataset.playbackStatus==='{status}'")
    def elapsed():
        return browser.js("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)")
    def measure_fps(frame_window='window'):
        return browser.js(f"new Promise(resolve=>{{let start=null,previous=null,frames=0,max=0;const tick=t=>{{if(start===null)start=t;if(previous!==null)max=Math.max(max,t-previous);previous=t;frames++;if(t-start>=3000)resolve({{fps:(frames-1)*1000/(t-start),max_frame_ms:max}});else {frame_window}.requestAnimationFrame(tick)}};{frame_window}.requestAnimationFrame(tick)}})")
    try:
        browser.until('window.ready')
        browser.viewport(1366)
        time.sleep(.5)
        for index,template in enumerate(['warehouse','airport','clinic']):
            browser.js(f'window.show({index})');browser.until(f"document.querySelector('.simulation-2d')?.dataset.template==='{['warehouse','airport','hospital'][index]}'")
            browser.until("document.querySelector('.simulation-controls')?.dataset.playbackStatus==='RUNNING'")
            click('Стоп');assert elapsed()==0
            for speed in [1,2,4]:
                browser.js(f"(()=>{{const x=document.querySelector('.simulation-controls select');x.value='{speed}';x.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
                browser.until(f"document.querySelector('.simulation-controls').dataset.playbackSpeed==='{speed}'")
                click('Старт');start=elapsed();wall=time.monotonic();time.sleep(2);click('Пауза');duration=time.monotonic()-wall;delta=elapsed()-start
                assert abs(delta/duration-60*speed)<60*speed*.25,(template,speed,delta,duration)
                paused=elapsed();time.sleep(.25);assert elapsed()==paused
                evidence['checks'].append({'template':template,'speed':speed,'model_seconds_per_wall_second':round(delta/duration,2),'pause_frozen':True})
            # Hidden document must freeze model time and resume without catching up.
            browser.js("Object.defineProperty(document,'hidden',{value:true,configurable:true})")
            click('Старт');frozen=elapsed();time.sleep(.3);assert elapsed()==frozen
            browser.js("Object.defineProperty(document,'hidden',{value:false,configurable:true})");click('Пауза')
            browser.js("(()=>{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'2500');x.dispatchEvent(new Event('input',{bubbles:true}))})()")
            browser.until("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)===150000")
            click('Перезапуск');browser.until("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)<200")
            click('Пауза')
            if template=='warehouse':
                browser.viewport(1366)
                evidence['checks'].append({'template':template,'width':1366,'view':'2D','benchmark':measure_fps()})
            click('3D')
            browser.until("window.messages.some(x=>x.type==='ROBCRAFT_REPORT'&&x.payload.versions.renderer_engine_version==='conditional-live-playback-v2')",timeout=30)
            browser.js("document.querySelectorAll('details').forEach(x=>x.open=true)")
            assert not browser.js("/\\b[CFRK]\\d{2}\\b|sha256:|[0-9a-f]{8}-[0-9a-f]{4}-/.test(document.body.innerText)")
            if template=='warehouse':
                evidence['gpu']=browser.js("(()=>{const canvas=document.querySelector('iframe').contentDocument.querySelector('canvas');const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');const ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)})()")
                for width in [1366,390]:
                    browser.viewport(width);click('Старт')
                    panel_height=browser.js("document.querySelector('iframe').getBoundingClientRect().height")
                    fps=measure_fps()
                    canvas=browser.js("(()=>{const c=document.querySelector('iframe').contentDocument.querySelector('canvas');return {width:c.width,height:c.height,clientWidth:c.clientWidth,clientHeight:c.clientHeight}})()")
                    browser.screenshot(f'warehouse-3d-{width}.png');click('Пауза')
                    assert abs(browser.js("document.querySelector('iframe').getBoundingClientRect().height")-panel_height)<1
                    horizontal=browser.js("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                    assert horizontal<=1,(width,horizontal)
                    evidence['checks'].append({'template':template,'width':width,'view':'3D',**fps,'canvas':canvas,'panel_height_px':panel_height,'horizontal_overflow_px':horizontal})
            click('2D');browser.viewport(1366);browser.screenshot(f'{template}-2d.png')
        print(json.dumps(evidence,ensure_ascii=False))
        (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        assert all(c.get('fps',30)>=30 for c in evidence['checks'] if c.get('view')=='3D'), 'FPS criterion not met on the recorded renderer'
    finally:
        (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
        server.shutdown();server.server_close()


if __name__=='__main__':main()
