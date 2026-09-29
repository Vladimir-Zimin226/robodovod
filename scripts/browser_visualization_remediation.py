"""Local synthetic control/clock/3D/GPU acceptance. Requires local Vite :5189."""
import json
import subprocess
import time
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from local_browser import LocalBrowser, ROOT

OUT = ROOT / '.test-visualization-remediation/final-browser'
HARNESS = ROOT / 'frontend/.test-visualization-final'


def main():
    HARNESS.mkdir(exist_ok=True)
    bundle = subprocess.check_output(['node', '--preserve-symlinks', '--input-type=module', '-e',
        "import {playbackCase} from './robcraft/tests/support/safe-case.js';const cases=['warehouse','airport','hospital'].map(x=>playbackCase(x,x==='warehouse'?11:x==='airport'?6:4));const multi=structuredClone(cases[0]);const s=multi.request.scenario_spec;const z={...s.zones[0],zone_id:'zone.second',label:'Вторая зона'};const t={...s.tasks[0],task_id:'task.second',zone_id:z.zone_id};const f={...s.fleet[0],fleet_id:'fleet.second',zone_id:z.zone_id,selected_fleet:3};s.zones.push(z);s.tasks.push(t);s.fleet.push(f);cases.push(multi);console.log(JSON.stringify(cases));"],cwd=ROOT)
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
    built=subprocess.run(['node','--preserve-symlinks','--preserve-symlinks-main','node_modules/vite/bin/vite.js','build','--configLoader','runner','--config',str(config)],cwd=ROOT/'frontend',capture_output=True,text=True)
    assert built.returncode==0,built.stdout+built.stderr
    shutil.copyfile(HARNESS/'fixture.json',dist/'.test-visualization-final/fixture.json')
    server=ThreadingHTTPServer(('127.0.0.1',5191),partial(SimpleHTTPRequestHandler,directory=str(dist)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    browser = LocalBrowser('http://127.0.0.1:5191/.test-visualization-final/index.html', OUT, software_gpu=True)
    evidence={'gpu':'not inspected','checks':[]}
    sizes=[(390,844),(768,1024),(1366,900),(1920,1080)]
    def viewport(width,height):
        browser.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<800})
    def click(label):
        browser.js(f"[...document.querySelectorAll('button')].find(x=>x.textContent==={json.dumps(label)}).click()")
        status={'Старт':'RUNNING','Перезапуск':'RUNNING','Стоп':'STOPPED','Пауза':'PAUSED'}.get(label)
        if status:
            browser.until(f"document.querySelector('.simulation-controls')?.dataset.playbackStatus==='{status}'")
    def elapsed():
        return browser.js("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)")
    def measure_fps(frame_window='window'):
        return browser.js(f"new Promise(resolve=>{{let start=null,previous=null,frames=0,max=0;const tick=t=>{{if(start===null)start=t;if(previous!==null)max=Math.max(max,t-previous);previous=t;frames++;if(t-start>=3000)resolve({{fps:(frames-1)*1000/(t-start),max_frame_ms:max,seconds:(t-start)/1000}});else {frame_window}.requestAnimationFrame(tick)}};{frame_window}.requestAnimationFrame(tick)}})")
    try:
        browser.until('window.ready')
        viewport(1366,900)
        time.sleep(.5)
        for index,template in enumerate(['warehouse','airport','clinic']):
            browser.js(f'window.show({index})');browser.until(f"document.querySelector('.simulation-2d')?.dataset.template==='{['warehouse','airport','hospital'][index]}'")
            browser.until("document.querySelector('.simulation-controls')?.dataset.playbackStatus==='RUNNING'")
            click('Стоп');assert elapsed()==0
            for speed in [.5,1,2,4]:
                browser.js(f"(()=>{{const x=document.querySelector('.simulation-controls select');x.value='{speed}';x.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
                browser.until(f"document.querySelector('.simulation-controls').dataset.playbackSpeed==='{speed}'")
                click('Старт');start=elapsed();wall=time.monotonic();time.sleep(2);click('Пауза');duration=time.monotonic()-wall;delta=elapsed()-start
                assert abs(delta/duration-60*speed)<60*speed*.30,(template,speed,delta,duration)
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
            browser.js("(()=>{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'180');x.dispatchEvent(new Event('input',{bubbles:true}))})()")
            browser.until("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)===10800")
            for width,height in sizes:
                viewport(width,height)
                geometry=browser.js("(()=>{const svg=document.querySelector('.facility-plan svg');const box=svg.getBoundingClientRect();return {svg_width:box.width,svg_height:box.height,robot_labels:[...svg.querySelectorAll('g[transform] text')].length,overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth}})()")
                browser.js("document.querySelector('.facility-plan svg').scrollIntoView({block:'center'})")
                browser.screenshot(f'{template}-2d-{width}.png')
                assert geometry['overflow']<=1,(template,width,geometry)
                evidence['checks'].append({'template':template,'width':width,'height':height,'view':'2D',**geometry})
            browser.js("(()=>{const original=URL.createObjectURL;URL.createObjectURL=blob=>{window.__visualExport=blob;return original.call(URL,blob)};[...document.querySelectorAll('button')].find(button=>button.textContent.includes('Сохранить открытый 2D-кадр')).click()})()")
            exported=browser.js("window.__visualExport.text().then(text=>({bytes:text.length,hasRobotLabel:text.includes('11')||text.includes('6')||text.includes('4'),hasCompletePlan:text.includes('viewBox')}))")
            assert exported['hasRobotLabel'] and exported['hasCompletePlan'],(template,exported)
            evidence['checks'].append({'template':template,'view':'SVG-export',**exported})
            viewport(1366,900)
            browser.js('window.messages=[]')
            click('3D')
            browser.until("window.messages.some(x=>x.type==='ROBCRAFT_REPORT'&&x.payload.versions.renderer_engine_version==='conditional-live-playback-v3')",timeout=30)
            browser.until("Boolean(document.querySelector('iframe')?.contentDocument?.querySelector('canvas')?.getContext('webgl'))",timeout=30)
            browser.until(f"document.querySelector('iframe')?.contentDocument?.querySelector('#hud-robots')?.textContent==='{11 if template=='warehouse' else 6 if template=='airport' else 4}'",timeout=30)
            browser.until("document.querySelector('iframe')?.contentDocument?.querySelector('#hud-time')?.textContent==='03:00'",timeout=30)
            time.sleep(.2)
            browser.js("document.querySelectorAll('details').forEach(x=>x.open=true)")
            assert not browser.js("/\\b[CFRK]\\d{2}\\b|sha256:|[0-9a-f]{8}-[0-9a-f]{4}-/.test(document.body.innerText)")
            if template=='warehouse':
                evidence['gpu']=browser.js("(()=>{const canvas=document.querySelector('iframe').contentDocument.querySelector('canvas');const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');const ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)})()")
            assert elapsed()==10800,(template,elapsed())
            browser.js("document.querySelector('iframe').scrollIntoView({block:'center'})")
            browser.screenshot(f'{template}-3d-overview.png')
            for speed in [.5,1,2,4]:
                browser.js(f"(()=>{{const x=document.querySelector('.simulation-controls select');x.value='{speed}';x.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
                browser.until(f"document.querySelector('.simulation-controls').dataset.playbackSpeed==='{speed}'")
                click('Старт');start=elapsed();wall=time.monotonic();time.sleep(1.5);click('Пауза');duration=time.monotonic()-wall;delta=elapsed()-start
                assert abs(delta/duration-48*speed)<48*speed*.30,(template,'3D',speed,delta,duration)
                evidence['checks'].append({'template':template,'view':'3D-tempo','speed':speed,'model_seconds_per_wall_second':round(delta/duration,2)})
            browser.js("(()=>{const x=document.querySelector('.simulation-controls input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(x,'180');x.dispatchEvent(new Event('input',{bubbles:true}))})()")
            browser.until("Number(document.querySelector('.simulation-controls').dataset.modelSeconds)===10800")
            for width,height in sizes:
                viewport(width,height)
                panel_height=browser.js("document.querySelector('iframe').getBoundingClientRect().height")
                browser.js("(()=>{const gl=document.querySelector('iframe').contentDocument.querySelector('canvas').getContext('webgl');if(!gl.__originalClear){gl.__originalClear=gl.clear.bind(gl);gl.__originalDraw=gl.drawArrays.bind(gl);gl.clear=(...args)=>{gl.__visualFrames++;return gl.__originalClear(...args)};gl.drawArrays=(...args)=>{gl.__drawCalls++;return gl.__originalDraw(...args)}}gl.__visualFrames=0;gl.__drawCalls=0})()")
                fps=measure_fps()
                counters=browser.js("(()=>{const gl=document.querySelector('iframe').contentDocument.querySelector('canvas').getContext('webgl');return {frames:gl.__visualFrames,draw_calls:gl.__drawCalls}})()")
                canvas=browser.js("(()=>{const c=document.querySelector('iframe').contentDocument.querySelector('canvas');return {width:c.width,height:c.height,clientWidth:c.clientWidth,clientHeight:c.clientHeight}})()")
                browser.js("document.querySelector('iframe').scrollIntoView({block:'center'})")
                browser.screenshot(f'{template}-3d-{width}.png')
                horizontal=browser.js("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                assert horizontal<=1,(template,width,horizontal)
                assert abs(browser.js("document.querySelector('iframe').getBoundingClientRect().height")-panel_height)<1
                evidence['checks'].append({'template':template,'width':width,'height':height,'view':'3D',**fps,'rendered_fps':counters['frames']/fps['seconds'],'draw_calls_per_frame':counters['draw_calls']/max(1,counters['frames']),'canvas':canvas,'panel_height_px':panel_height,'horizontal_overflow_px':horizontal})
            button=browser.js("(()=>{const f=document.querySelector('iframe');const a=f.getBoundingClientRect();const b=f.contentDocument.querySelector('#manual-toggle').getBoundingClientRect();return {x:a.left+b.left+b.width/2,y:a.top+b.top+b.height/2}})()")
            browser.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':button['x'],'y':button['y'],'button':'left','clickCount':1})
            browser.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':button['x'],'y':button['y'],'button':'left','clickCount':1})
            time.sleep(.25)
            manual=browser.js("(()=>{const d=document.querySelector('iframe').contentDocument;return {mode:d.querySelector('#camera-mode').textContent,pointer_locked:Boolean(d.pointerLockElement)}})()")
            assert manual['pointer_locked'],(template,manual)
            browser.screenshot(f'{template}-3d-manual.png')
            evidence['checks'].append({'template':template,'view':'manual-camera',**manual})
            click('2D');assert elapsed()==10800
        browser.js('window.show(3)')
        browser.until("document.querySelector('.simulation-2d')?.dataset.template==='warehouse'")
        browser.until("document.querySelector('.simulation-controls')?.dataset.playbackStatus==='RUNNING'")
        click('Пауза')
        select="[...document.querySelectorAll('.simulation-2d-header label')].find(x=>x.textContent.includes('Рабочая зона')).querySelector('select')"
        browser.js(f"(()=>{{const x={select};x.value='zone.second';x.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
        browser.until("document.querySelector('.facility-plan-heading').textContent.includes('3 роботов')")
        click('3D')
        browser.until("document.querySelector('iframe')?.contentDocument?.querySelector('#hud-robots')?.textContent==='3'",timeout=30)
        browser.js(f"(()=>{{const x={select};x.value='zone.terminal';x.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
        browser.until("document.querySelector('iframe')?.contentDocument?.querySelector('#hud-robots')?.textContent==='11'",timeout=30)
        evidence['checks'].append({'template':'warehouse','view':'zone-switch','second_zone_3d_robots':3,'first_zone_3d_robots':11})
        print(json.dumps(evidence,ensure_ascii=False))
        (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        assert all(c.get('rendered_fps',0)>=30 for c in evidence['checks'] if c.get('view')=='3D'), '3D rendered FPS criterion not met on the recorded renderer'
    finally:
        (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
        server.shutdown();server.server_close()


if __name__=='__main__':main()
