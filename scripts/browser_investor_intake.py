"""Local browser proof: three loader clicks and native investor PDF download.

Normalization and capacity DTO validation use real backend code. Candidate
ranking and capacity save are fixtures in memory, with no database or writes
to backup. The PDF routes use the real owner-scoped API with in-memory loaders.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import websocket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'scripts'))
from auth import require_auth_context
from calculation.intake import CalculationIntakeRequestV2, normalize_intake
from calculation_contracts import parse_capacity_analysis_request
from database import database_session
from evidence_export_api import create_evidence_export_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from investor_report_smoke import saved_run


ENTRY = r'''import React from 'react';
import {createRoot} from 'react-dom/client';
import ProcessRoleIntakeV2 from '/src/components/ProcessRoleIntakeV2.jsx';
import {AppShell} from '/src/components/AppShell.jsx';
import {EvidenceExportSession} from '/src/evidenceExportApi.js';
import '/src/index.css';
const config=await (await fetch('./config.json')).json();
const original=window.fetch.bind(window);
window.__errors=[];
window.addEventListener('error',e=>window.__errors.push(e.message));
window.addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));
window.fetch=(input,options={})=>{
 const path=new URL(String(input),location.href);
 return path.pathname.startsWith('/api/') ? original(config.bridge+path.pathname+path.search,{...options,credentials:'omit'}) : original(input,options);
};
const kind=new URLSearchParams(location.search).get('kind')||'retail';
const project={id:config.projectId,name:'Локальная проверка',profile:{}};
window.downloadReport=async()=>{
 const session=new EvidenceExportSession();
 await session.downloadInvestorReport(config.projectId,config.runId);
 window.__downloaded=true;
};
createRoot(document.getElementById('root')).render(<AppShell activeNav={kind} user={{role:'ADMIN'}} activeProject={project} onNavigate={()=>{}}>
 <ProcessRoleIntakeV2 objectType={kind} activeProject={project} onCapacityResult={(response,payload)=>window.__saved={response,payload}}/>
</AppShell>);
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:5188')
    args = parser.parse_args()
    output = ROOT/'.tmp/investor-browser'
    output.mkdir(parents=True,exist_ok=True)
    source_files = list((ROOT/'backup').rglob('*.jsonl'))
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    rows = [json.loads(l) for l in (ROOT/'backup/database/analysis_runs.jsonl').read_text('utf-8').splitlines()]
    by_id = {r['id']:r for r in rows}
    full_row = max((r for r in rows if (r.get('result_snapshot') or {}).get('schema_version')=='commercial-scenarios-bundle-v3'),key=lambda r:r['finished_at'])
    run = saved_run(full_row)
    linked = saved_run(by_id[full_row['input_snapshot']['capacity_run_id']])
    capacity_rows = {kind:next(r for r in reversed(rows) if r['run_kind']=='CAPACITY_ANALYSIS'
        and r['status']=='SUCCEEDED' and r['input_snapshot']['process']['process_code']==code) for kind,code in [
        ('warehouse','warehouse_receiving_shipping'),('airport','airport_terminal_cleaning'),('clinic','clinic_food')]}
    owner = uuid.uuid4()
    def loader(_db,project_id,run_id,owner_id):
        return {run.run_id:run,linked.run_id:linked}.get(str(run_id)) if str(project_id)==run.project_id and owner_id==owner else None
    app = FastAPI()
    app.include_router(create_evidence_export_router(loader,loader))
    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=owner))
    app.dependency_overrides[database_session] = lambda: object()
    client = TestClient(app)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(204); self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Allow-Headers','Content-Type, X-CSRF-Token')
            self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS'); self.end_headers()

        def respond(self,body,content_type='application/json',headers=None,status=200):
            if isinstance(body,dict): body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status); self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)));self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Expose-Headers','ETag,X-Report-Source-Digest,X-Report-Presentation,X-Simulation-Report-Digest')
            for key,value in (headers or {}).items():
                if key.lower() not in {'content-length','content-type'}: self.send_header(key,value)
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path=='/api/catalog/models':
                kind = parse_qs(parsed.query)['object_kind'][0]
                row = capacity_rows[kind]
                self.respond({'items':[{'name':'Модель сохранённого сценария','model_id':row['input_snapshot']['model_id'],
                    'position_id':row['input_snapshot']['position_id'],'calculation_ready':True,
                    'calculation_profile':'CLEANING_AREA_V1' if kind=='airport' else 'TRANSPORT_CYCLE_V1',
                    'maturity_status':'SERIAL','selection':{'status':'REQUIRES_CHECK'}}]})
            elif parsed.path.startswith('/api/'):
                response=client.get(self.path)
                self.respond(response.content,response.headers.get('Content-Type'),response.headers,response.status_code)
            else: self.send_error(404)

        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            try:
                if self.path.endswith('/normalize'):
                    response=normalize_intake(CalculationIntakeRequestV2.model_validate(body)).model_dump(mode='json')
                elif self.path.endswith('/preview'):
                    request=body['capacity_request']
                    parse_capacity_analysis_request(request)
                    response={'candidates':[{'position_id':request['position_id'],'technical_score':'1','status':'INCLUDED'}]}
                elif self.path.endswith('/capacity-analyses'):
                    request=parse_capacity_analysis_request(body)
                    row=next(r for r in capacity_rows.values() if r['input_snapshot']['process']['process_code']==request.process.process_code)
                    response=json.loads(json.dumps(row['result_snapshot']))
                    response['input_revision']=body['input_revision']
                    response['trace']['envelope']['input_revision']=body['input_revision']
                    response['capacity']['process_id']=body['process']['process_id']
                    response['trace']['envelope']['process_id']=body['process']['process_id']
                else: raise ValueError('Unexpected request')
                self.respond(response)
            except Exception as exc: self.respond({'detail':str(exc)},status=422)

        def log_message(self,*args): pass

    with http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler) as bridge:
        thread=threading.Thread(target=bridge.serve_forever);thread.start()
        base=f'http://127.0.0.1:{bridge.server_port}'
        harness=ROOT/'frontend/.tmp-investor-browser'
        harness.mkdir(exist_ok=True)
        (harness/'index.html').write_text('<div id="root"></div><script type="module" src="./entry.jsx"></script>',encoding='utf-8')
        (harness/'entry.jsx').write_text(ENTRY,encoding='utf-8')
        (harness/'config.json').write_text(json.dumps({'bridge':base,'projectId':run.project_id,'runId':run.run_id}),encoding='utf-8')
        profile=Path(tempfile.mkdtemp(prefix='investor-chrome-',dir=ROOT/'.tmp'))
        chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        process=subprocess.Popen([str(chrome),'--headless=new','--no-first-run','--no-default-browser-check',
            '--remote-debugging-port=0','--remote-allow-origins=*',f'--user-data-dir={profile}','about:blank'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        ws=None
        try:
            active=profile/'DevToolsActivePort'
            deadline=time.monotonic()+20
            while not active.exists() and time.monotonic()<deadline: time.sleep(.1)
            port=active.read_text('utf-8').splitlines()[0]
            tabs=json.loads(urlopen(f'http://127.0.0.1:{port}/json').read())
            ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'),timeout=15)
            serial=0
            def call(method,params=None):
                nonlocal serial
                serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
                while True:
                    reply=json.loads(ws.recv())
                    if reply.get('id')==serial:
                        assert 'error' not in reply,reply
                        return reply.get('result',{})
            def js(source,await_promise=False):
                result=call('Runtime.evaluate',{'expression':source,'returnByValue':True,'awaitPromise':await_promise})
                assert 'exceptionDetails' not in result,result
                return result.get('result',{}).get('value')
            def until(source):
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    if value:=js('Boolean('+source+')'): return value
                    time.sleep(.1)
                raise AssertionError(source+'; '+str(js('document.body.innerText.slice(-1400)')))
            def click(label):
                js("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(label)+").click()")
            results=[]
            for width,height in [(1366,768),(390,700)]:
                call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
                for kind,noun in [('retail','склад'),('airport','аэропорт'),('clinic','объект клиники')]:
                    call('Page.navigate',{'url':args.url+'/.tmp-investor-browser/?kind='+kind})
                    until("document.querySelector('.typical-object-action')")
                    click('Загрузить типовой '+noun+' организаторов')
                    assert js("[...document.querySelectorAll('input[type=checkbox]')].filter(i=>i.closest('label')?.textContent.includes('Подтверж')).every(i=>i.checked)")
                    click('Проверить ввод')
                    until("[...document.querySelectorAll('button')].some(b=>b.textContent==='Рассчитать и сохранить'&&!b.disabled)")
                    click('Рассчитать и сохранить')
                    until('window.__saved')
                    assert not js('window.__errors'),js('window.__errors')
                    assert js('document.documentElement.scrollWidth<=innerWidth+1')
                    assert js("document.querySelector('.sidebar-footer a').href")=='https://www.zmncraft.ru/'
                    assert not js("document.querySelector('.sidebar-footer').innerText.includes('v1.0')")
                    (output/f'{kind}-{width}.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']))
                    results.append({'object':kind,'width':width,'clicks':3,'status':'PASS'})
            call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(output)})
            js('window.downloadReport()',True)
            until('window.__downloaded')
            pdf=client.get(f'/api/projects/{run.project_id}/analysis-runs/{run.run_id}/exports/investor-report.pdf').content
            deadline=time.monotonic()+10
            downloads=[]
            while time.monotonic()<deadline:
                downloads=list(output.glob('*.pdf'))
                if downloads and downloads[0].read_bytes()==pdf: break
                time.sleep(.1)
            assert downloads and downloads[0].read_bytes()==pdf,'PDF bytes differ'
            assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
            (output/'verification.json').write_text(json.dumps({'flows':results,'native_pdf_download':'PASS','backup_files_unchanged':len(before)},ensure_ascii=False,indent=2),encoding='utf-8')
            print('PASS: six object/viewport flows, exactly three clicks; native investor PDF matches API bytes; backup unchanged')
        finally:
            if ws: ws.close()
            process.terminate();process.wait(timeout=10)
            bridge.shutdown();thread.join()


if __name__=='__main__': main()
