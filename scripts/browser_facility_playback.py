"""Read saved clinic/airport cases from backup; exercise real App and WebGL locally.

Auth/history/evidence are served in browser memory. No database/server writes.
Requires local Vite on --url (default localhost:5173), Chrome and websocket-client.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from urllib.request import urlopen

import websocket

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

ENTRY = r'''import React from 'react';
import {createRoot} from 'react-dom/client';
import App from '/src/App.jsx';
import '/src/index.css';
const fixtures=await (await fetch('./cases.json')).json();
const selected=new URLSearchParams(location.search).get('template')||'airport';
const data=fixtures[selected];
const nativeFetch=window.fetch.bind(window);
const project={id:data.request.project_id,name:'Браузерная проверка объекта',profile:{timezone:'Asia/Sakhalin'},scenarios:[]};
const run=data.run;
const listing=Array.from({length:16},(_,i)=>({...run,id:`browser-history-${i}`,run_kind:'CAPACITY_ANALYSIS',created_at:'2026-09-29T10:00:00Z'})).concat(run);
window.__messages=[];window.__errors=[];
window.addEventListener('message',e=>{if(e.data?.type?.startsWith('ROBCRAFT')||e.data?.type==='SCENARIO_LOADED') window.__messages.push(e.data)});
window.addEventListener('error',e=>window.__errors.push(e.error?.stack||e.message));
window.addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));
window.fetch=async (input,options={})=>{
 const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;
 if(!path.startsWith('/api/'))return nativeFetch(input,options);
 if(options.method && options.method!=='GET')throw new Error('Browser check forbids writes: '+path);
 let value;
 if(path==='/api/auth/me')value={user:{id:'browser-user',email:'browser@example.test',role:'ADMIN'}};
 else if(path==='/api/projects')value={items:[project]};
 else if(path.includes('/candidate-comparisons/'))value={items:[],source_position_id:null};
 else if(path.includes('/simulations/')&&path.endsWith('/evidence'))value={items:[{request:data.request,report:data.report}]};
 else if(path.endsWith('/analysis-runs'))value={items:listing};
 else if(path.includes('/analysis-runs/'))value=run;
 else if(path==='/api/projects/'+project.id)value=project;
 else value={};
 return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
};
createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:5173')
    parser.add_argument('--backup', type=Path, default=ROOT / 'backup/database')
    args = parser.parse_args()
    source_files = [args.backup / 'simulation_artifacts.jsonl', args.backup / 'analysis_runs.jsonl']
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    artifacts = [json.loads(line) for line in source_files[0].read_text(encoding='utf-8').splitlines()]
    runs = {r['id']: r for r in map(json.loads, source_files[1].read_text(encoding='utf-8').splitlines())}
    cases = {}
    for template in ('airport', 'hospital'):
        saved = next(a for a in reversed(artifacts) if a['request_snapshot']['scenario_spec']['template'] == template)
        cases[template] = {'request': saved['request_snapshot'], 'report': saved['report_snapshot'], 'run': runs[saved['analysis_run_id']]}
    harness = Path(tempfile.mkdtemp(prefix='.tmp-facility-', dir=ROOT / 'frontend'))
    profile = Path(tempfile.mkdtemp(prefix='facility-chrome-', dir=ROOT / '.tmp'))
    output = ROOT / '.tmp/facility-browser-20260928'
    output.mkdir(parents=True, exist_ok=True)
    (harness / 'index.html').write_text('<div id="root"></div><script type="module" src="./entry.jsx"></script>', encoding='utf-8')
    (harness / 'entry.jsx').write_text(ENTRY, encoding='utf-8')
    (harness / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
    chrome = subprocess.Popen([str(CHROME), '--headless=new', '--no-first-run', '--no-default-browser-check',
        '--disable-extensions', '--disable-background-networking', '--disable-component-update',
        '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--remote-allow-origins=*',
        '--remote-debugging-port=0', f'--user-data-dir={profile}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    seq = 0
    events=[]

    def call(method, params=None):
        nonlocal seq
        seq += 1
        ws.send(json.dumps({'id': seq, 'method': method, 'params': params or {}}))
        while True:
            response = json.loads(ws.recv())
            if response.get('method'): events.append(response)
            if response.get('id') == seq:
                if 'error' in response: raise RuntimeError(response['error'])
                return response.get('result', {})

    def js(source):
        result = call('Runtime.evaluate', {'expression': source, 'returnByValue': True, 'awaitPromise': True})
        if result.get('exceptionDetails'): raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def until(source, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = js(source)
            if value: return value
            errors=js('window.__errors')
            if errors: raise AssertionError(errors)
            time.sleep(.1)
        raise AssertionError('Timeout: '+source+'; errors='+str(js('window.__errors'))+'; '+str(js('document.body.innerText.slice(-1600)')))

    def button(text):
        js("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(text, ensure_ascii=False)+").click()")

    def screenshot(name, selector=None):
        params = {'format':'png', 'captureBeyondViewport':True}
        if selector:
            rect=js("(()=>{const r=document.querySelector("+json.dumps(selector)+").getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()")
            params['clip']=rect
        data=call('Page.captureScreenshot',params)['data']
        (output / name).write_bytes(base64.b64decode(data))

    def child_state():
        child_errors=js("document.querySelector('iframe').contentWindow.__browserErrors")
        assert not child_errors,child_errors
        call('Debugger.enable')
        events.clear()
        line=next(i for i,line in enumerate((ROOT/'robcraft/src/main.js').read_text(encoding='utf-8').splitlines()) if "if (cameraState === 'AUTOPILOT') updateFacilityCamera" in line)
        bp=call('Debugger.setBreakpointByUrl',{'lineNumber':line,'urlRegex':r'/robcraft/src/main\.js'})
        breakpoint=bp['breakpointId']
        try:
            while not any(e.get('method')=='Debugger.paused' for e in events):
                event=json.loads(ws.recv());events.append(event)
            paused=next(e for e in reversed(events) if e.get('method')=='Debugger.paused')
            result=call('Debugger.evaluateOnCallFrame',{'callFrameId':paused['params']['callFrames'][0]['callFrameId'],
                'expression':'({hasPlan:!!scene.facilityPlan,hasReport:!!authoritativeSimulationReport,playback:embeddedPlayback,modified:simulation.sceneModified,frame:simulation.facilityFrame,robots:simulation.robots.map(r=>({position:r.position,state:r.state}))})','returnByValue':True})
            return result['result'].get('value')
        finally:
            call('Debugger.removeBreakpoint',{'breakpointId':breakpoint})
            if any(e.get('method')=='Debugger.paused' for e in events): call('Debugger.resume')
            call('Debugger.disable')

    try:
        active = profile / 'DevToolsActivePort'
        for _ in range(150):
            if active.exists(): break
            time.sleep(.1)
        port=active.read_text().splitlines()[0]
        pages=json.load(urlopen(f'http://127.0.0.1:{port}/json/list'))
        ws=websocket.create_connection(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'),timeout=10)
        call('Page.enable'); call('Runtime.enable')
        call('Page.addScriptToEvaluateOnNewDocument', {'source': "window.__browserErrors=[];window.addEventListener('error',e=>window.__browserErrors.push(e.error?.stack||e.message));const draw=WebGLRenderingContext.prototype.drawArrays;WebGLRenderingContext.prototype.drawArrays=function(...args){window.__draws=(window.__draws||0)+1;return draw.apply(this,args)}"})
        results=[]
        for template in ('airport','hospital'):
            call('Emulation.setDeviceMetricsOverride', {'width':1366,'height':900,'deviceScaleFactor':1,'mobile':False})
            call('Page.navigate',{'url':f'{args.url}/{harness.name}/index.html?template={template}#reports'})
            until("document.querySelectorAll('.reports-card').length===17")
            js("document.querySelector('.reports-card:last-child').scrollIntoView();window.scrollTo(0,document.body.scrollHeight)")
            assert js('scrollY')>500
            js("[...document.querySelectorAll('.reports-card:last-child button')].find(b=>b.textContent==='Открыть').click()")
            until("document.querySelector('.facility-plan svg')!==null")
            assert js('scrollY')==0, 'result did not open at page top'
            time.sleep(.3)
            assert js('scrollY')==0, 'async report loading moved viewport'
            assert js("document.querySelector('iframe')===null"), 'hidden WebGL instance still running'
            button('Пауза'); button('Перезапуск'); time.sleep(.15); button('Пауза')
            screenshot(template+'-2d.png','.facility-plan')
            button('3D')
            until("window.__messages.some(m=>m.type==='SCENARIO_LOADED'&&m.payload.status==='APPLIED')")
            js("document.querySelector('iframe').scrollIntoView({block:'center'})")
            until("document.querySelector('iframe').contentWindow.__draws>100")
            js("window.__childClock=null;document.querySelector('iframe').contentWindow.addEventListener('message',e=>{if(e.data?.type==='SET_PLAYBACK')window.__childClock=e.data.payload})")
            button('Перезапуск'); time.sleep(.4); button('Пауза')
            until('window.__childClock?.status==="PAUSED"')
            state=child_state()
            assert state.get('frame'), {k:v for k,v in state.items() if k!='robots'}
            assert abs(state['frame']['elapsedSeconds']-state['playback']['elapsed_seconds'])<.001
            assert state['hasPlan'] and state['hasReport'] and not state['modified']
            for pose,robot in zip(state['frame']['robots'],state['robots']):
                assert robot['position']==[pose['x']-24,.42,pose['y']-16]
            frozen=js('window.__childClock.elapsed_seconds');time.sleep(.25)
            assert js('window.__childClock.elapsed_seconds')==frozen
            screenshot(template+'-3d.png','.robcraft-frame')
            button('Старт');time.sleep(.4)
            a=js('window.__childClock.elapsed_seconds');a_wall=time.monotonic();time.sleep(2);b=js('window.__childClock.elapsed_seconds');b_wall=time.monotonic()
            js("(()=>{const el=document.querySelector('.simulation-controls select');const set=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;set.call(el,'4');el.dispatchEvent(new Event('change',{bubbles:true}));})()")
            until('window.__childClock?.speed===4')
            c=js('window.__childClock.elapsed_seconds');c_wall=time.monotonic();time.sleep(2);d=js('window.__childClock.elapsed_seconds');d_wall=time.monotonic()
            speed_ratio=((d-c)/(d_wall-c_wall))/((b-a)/(b_wall-a_wall))
            assert speed_ratio>2.4,(a,b,c,d,speed_ratio)
            button('Пауза');time.sleep(.1)
            accelerated=child_state()
            assert accelerated['frame']['elapsedSeconds']>state['frame']['elapsedSeconds']
            assert abs(accelerated['frame']['elapsedSeconds']-accelerated['playback']['elapsed_seconds'])<.001
            screenshot(template+'-3d-active.png','.robcraft-frame')
            button('Стоп');until('window.__childClock?.elapsed_seconds===0')
            stopped=child_state();assert stopped['frame']['elapsedSeconds']==0
            js("window.__savedIframe=document.querySelector('iframe');true")
            button('2D');button('Старт');time.sleep(.2)
            assert js("document.querySelector('iframe')===window.__savedIframe"), 'switching views discarded 3D/editor state'
            assert js('window.__childClock.status')=='PAUSED'
            button('3D');js("document.querySelector('iframe').scrollIntoView({block:'center'})")
            until('window.__childClock.status==="RUNNING"')
            until('window.__childClock.elapsed_seconds>0')
            button('Пауза');time.sleep(.1)
            assert child_state()['frame']['elapsedSeconds']>0
            assert js('window.__errors')==[], js('window.__errors')
            assert not js("window.__messages.some(m=>m.type==='ROBCRAFT_ERROR')"), '3D protocol error'
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            button('2D');time.sleep(.3)
            assert js('document.documentElement.scrollWidth<=innerWidth+1'), 'mobile horizontal overflow'
            screenshot(template+'-mobile.png','.facility-plan')
            results.append({'template':template,'scroll_top':True,'webgl':True,'same_2d_3d_positions':True,'pause_stop_restart':True,'speed_ratio':round(speed_ratio,2),'mobile_width':390})
        (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(results,ensure_ascii=False),flush=True)
    finally:
        if ws: ws.close()
        subprocess.run(['taskkill','/PID',str(chrome.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try: chrome.wait(timeout=5)
        except subprocess.TimeoutExpired: chrome.kill();chrome.wait(timeout=5)
        for directory,prefix in ((harness,'.tmp-facility-'),(profile,'facility-chrome-')):
            if directory.resolve().is_relative_to(ROOT.resolve()) and directory.name.startswith(prefix):
                def writable_remove(function,path,error):
                    if function not in (os.unlink,os.rmdir) or not Path(path).resolve().is_relative_to(directory.resolve()): raise error
                    os.chmod(path,stat.S_IWRITE);function(path)
                for attempt in range(20):
                    try: shutil.rmtree(directory,onexc=writable_remove);break
                    except PermissionError:
                        if attempt==19: print('Chrome cache cleanup pending: '+directory.name,flush=True)
                        else: time.sleep(.2)
        assert before == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}, 'backup changed'


if __name__=='__main__':main()
