"""Local component acceptance; mocked HTTP, actual server finance, isolated Chrome.

Run Vite on 127.0.0.1:5189 first. Never contacts application storage or an LLM.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from economics_final import execute_economics_v4
from economics_partial import execute_partial_economics_v2
from test_economics_partial import _context
from test_evgeny_project import project_input

WORK = ROOT / ".test-product-remediation"
HARNESS = ROOT / "frontend/.test-product-remediation"


def main():
    baseline = "--baseline" in sys.argv
    stage1 = "--stage1" in sys.argv
    WORK.mkdir(exist_ok=True)
    HARNESS.mkdir(exist_ok=True)
    snapshot, context = _context()
    original = project_input()
    edited = {**original, "raas_monthly_per_robot_gross": "120000"}
    results = [execute_partial_economics_v2(raw, snapshot, context, full_engine=execute_economics_v4).result_snapshot
               for raw in (original, edited)]
    fixture = {"input": original, "results": results}
    (HARNESS / "fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
    (HARNESS / "harness.html").write_text('''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body><div id="root"></div><script type="module">
import React from 'react';
import {createRoot} from 'react-dom/client';
import Warehouse2DPlan from '/src/components/Warehouse2DPlan.jsx';
import ProjectWhatIf from '/src/components/ProjectWhatIf.jsx';
import BrainModelScreen from '/src/components/BrainModelScreen.jsx';
import '/src/index.css';
const root=createRoot(document.getElementById('root'));
window.fixture=await (await fetch('./fixture.json')).json();
window.requests=[]; window.saved=[]; window.pending=[]; window.mockMode='normal';
window.fetch=async (url,options={})=>{
 const body=options.body ? JSON.parse(options.body) : null; window.requests.push({url,body});
 if(window.mockMode==='hold') return new Promise(resolve=>window.pending.push({url,body,resolve}));
 if(url.includes('/api/brain/projects/')) return new Response(JSON.stringify(window.brainRecord),{status:200});
 if(url.includes('/api/catalog/')) return new Response(JSON.stringify({items:[],defaults:[]}),{status:200});
 if(url.endsWith('/preview')) return new Response(JSON.stringify({source_run_id:'source',source_result_sha256:'digest',capacity_run_id:'capacity',
 input_sha256:await window.hash(body.input),result:window.fixture.results[1]}),{status:200});
 window.saved.push(body); return new Response(JSON.stringify({id:'new-run',input_snapshot:{economics:body.input},result_snapshot:window.fixture.results[1]}),{status:201});
};
window.hash=async value=>{ const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
 return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(canonical(value)))))].map(x=>x.toString(16).padStart(2,'0')).join(''); };
window.showWarehouse=stage=>{
 const point=(id,x,y)=>({id,x,y,label:id});const waiting=point('waiting',50,200),pickup=point('pickup',130,200),dropoff=point('dropoff',430,200);
 const zone={id:'zone',label:'Учебная зона',x:0,y:0,width:500,height:280,geometrySource:'ASSUMED',racks:[],waiting,receiving:pickup,shipping:dropoff};
 const robots=Array.from({length:11},(_,lane)=>({id:'robot'+lane,lane,zoneId:'zone',stage,cargoState:'ON_ROBOT',x:50,y:200,points:{waiting,pickup,dropoff}}));
 root.render(React.createElement('main',{style:{maxWidth:'1024px',margin:'auto'}},React.createElement(Warehouse2DPlan,{scene:{zones:[zone],tasks:[],missingTasks:[]},frame:{robots},selectedZoneId:'zone'}),React.createElement('div',{id:'after'},'Следующий блок')));
};
window.showFinance=(id='source')=>root.render(React.createElement(ProjectWhatIf,{project:{id:'project',name:'Учебный проект'},run:{id,scenario_id:'scenario',result_sha256:'digest',input_snapshot:{capacity_run_id:'capacity',economics:window.fixture.input},result_snapshot:window.fixture.results[0]},onComplete:run=>{window.completed=run;}}));
window.brainRecord={profile:{profile_version:0,fields:{},model_status:'IDLE',active_processes:[]},versions:[],readiness:{technical:{missing:[]},labour:{missing:[]},next_question:{text:'Какой у вас объект?'}},usage:{}};
window.showBrain=(id='project')=>root.render(React.createElement(BrainModelScreen,{key:id,project:{id,name:id},user:{id:'user'}}));
window.ready=true;
</script></body></html>''', encoding="utf-8")
    if baseline:
        css = subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "show", "HEAD:frontend/src/index.css"]).decode("utf-8")
        (HARNESS / "baseline.css").write_text(css, encoding="utf-8")
    profile = WORK / f"chrome-{time.time_ns()}"
    chrome = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new", "--disable-gpu",
        "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*", "--remote-debugging-port=0",
        f"--user-data-dir={profile}", "http://127.0.0.1:5189/.test-product-remediation/harness.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    try:
        deadline = time.monotonic() + 20
        while not (profile / "DevToolsActivePort").exists():
            assert time.monotonic() < deadline, "Chrome did not start"
            time.sleep(.1)
        port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
        tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
        ws = websocket.create_connection(next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page"), timeout=20)
        counter = 0

        def call(method, params=None):
            nonlocal counter
            counter += 1
            ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            while True:
                response = json.loads(ws.recv())
                if response.get("id") == counter:
                    assert "error" not in response, response
                    return response.get("result", {})

        def js(source):
            response = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
            assert "exceptionDetails" not in response, response
            return response.get("result", {}).get("value")

        def until(source):
            end = time.monotonic() + 15
            while time.monotonic() < end:
                value = js(source)
                if value:
                    return value
                time.sleep(.1)
            raise AssertionError((source, js("document.body.innerText.slice(-1500)")))

        until("window.ready")
        if baseline:
            js("(()=>{let link=document.createElement('link');link.rel='stylesheet';link.href='./baseline.css';document.head.append(link)})()")
            time.sleep(.2)
            js("document.querySelectorAll('style[data-vite-dev-id]').forEach(el=>el.remove())")
        evidence = {"mode": "baseline" if baseline else "acceptance", "layout": [], "finance": {}}
        for width in (1366, 390):
            call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width == 390})
            js("window.showWarehouse('WAITING')")
            until("!!document.querySelector('.warehouse-robot-states')")
            time.sleep(.2)
            before = js("({height:document.querySelector('.warehouse-robot-states').getBoundingClientRect().height,after:document.querySelector('#after').getBoundingClientRect().top,canvas:document.querySelector('svg').getBoundingClientRect().height})")
            js("window.showWarehouse('TO_PICKUP')")
            until("document.querySelector('.warehouse-robot-states').innerText.includes('Едет')")
            after = js("({height:document.querySelector('.warehouse-robot-states').getBoundingClientRect().height,after:document.querySelector('#after').getBoundingClientRect().top,canvas:document.querySelector('svg').getBoundingClientRect().height})")
            evidence["layout"].append({"width": width, "before": before, "after": after, "shift": after["after"] - before["after"]})
            if not baseline:
                assert before == after, evidence["layout"]
            (WORK / f"layout-{width}.png").write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        if stage1:
            js("window.showBrain()")
            until("!!document.querySelector('textarea')")
            js("window.mockMode='hold'; (()=>{const el=document.querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(el,'220 паллет в сутки');el.dispatchEvent(new Event('input',{bubbles:true}));})()")
            until("!document.querySelector('form button').disabled")
            js("document.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));document.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
            until("window.pending.some(x=>x.url.endsWith('/turn'))")
            assert js("window.pending.filter(x=>x.url.endsWith('/turn')).length") == 1
            js("window.mockMode='normal';window.showBrain('second-project')")
            until("document.body.innerText.includes('second-project') && !!document.querySelector('textarea')")
            js("window.pending.find(x=>x.url.endsWith('/turn')).resolve(new Response(JSON.stringify({profile:{profile_version:999,fields:{},model_status:'MODEL'},readiness:{technical:{missing:[]},labour:{missing:[]}}}),{status:200}))")
            time.sleep(.2)
            assert not js("document.body.innerText.includes('999')")
            evidence['brain'] = {'double_send_count': 1, 'late_project_response_ignored': True}
            (WORK / 'stage1-browser.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(evidence, ensure_ascii=False))
            return
        js("window.showFinance()")
        until("!!(document.querySelector('input[type=number]') || document.querySelector('button'))")
        if not baseline:
            js("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Сценарии и пересчёт')).click()")
            until("!!document.querySelector('[role=dialog]')")
        else:
            js("document.querySelector('details').open=true")
        evidence["finance"]["before"] = js("document.body.innerText")
        js("(()=>{const el=document.querySelector('input[aria-label=\"RaaS, ₽/робот/месяц\"]') || document.querySelector('input[type=number]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'120000');el.dispatchEvent(new Event('input',{bubbles:true}));})()")
        until("window.requests.some(x=>x.url.endsWith('/preview'))")
        time.sleep(.3)
        evidence["finance"]["after"] = js("document.body.innerText")
        evidence["finance"]["purchase_unchanged"] = results[0]["scenarios"][1]["report_facts"]["project_npv"] == results[1]["scenarios"][1]["report_facts"]["project_npv"]
        evidence["finance"]["requests"] = js("window.requests")
        (WORK / f"{'baseline' if baseline else 'acceptance'}-browser.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"mode": evidence["mode"], "layout": evidence["layout"], "finance_preview_calls": len(evidence["finance"]["requests"])}, ensure_ascii=False))
    finally:
        if ws:
            ws.close()
        chrome.terminate()
        chrome.wait(timeout=10)


if __name__ == "__main__":
    main()
