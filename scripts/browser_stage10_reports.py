"""Exercise the stage 10 report route against a static, mocked owner session."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.request import urlopen

import websocket


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend/dist"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class QuietHandler(SimpleHTTPRequestHandler):
    injected_script = ""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            source = (DIST / "index.html").read_text(encoding="utf-8")
            payload = source.replace("<head>", f"<head><script>{self.injected_script}</script>", 1).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


def fixture():
    project = {"id": "project-a", "name": "Склад А", "scenarios": [{"id": "scenario-base", "slot": "BASE", "inputs": {}}]}
    def summary(group, zone, fleet, kind, purchase=None, raas=None, editable=False):
        return {"group_run_id": group, "zone_label": zone, "process_code": "warehouse_receiving_shipping",
            "model_name": "MULE", "fleet": fleet, "result_type": kind, "can_create_version": editable,
            "branches": {"capacity": "CALCULATED", "labour": "CALCULATED" if purchase else "NOT_CALCULATED",
                         "purchase": "CALCULATED" if purchase else "NOT_CALCULATED",
                         "raas": "CALCULATED" if raas else "NOT_CALCULATED", "simulation": "NOT_SAVED"},
            "npv": ([{"acquisition": "PURCHASE", "uncertainty": "BASE", "value": purchase, "unit": "RUB"}] if purchase else [])
                + ([{"acquisition": "RAAS", "uncertainty": "BASE", "value": raas, "unit": "RUB"}] if raas else []),
            "completeness": {"inputs": {"confirmed": 12 if purchase else 4, "total": 24},
                             "branches_calculated": 3 if purchase else 1, "branches_total": 5}}
    def run(id, kind, created, report):
        return {"id": id, "project_id": project["id"], "run_kind": kind, "status": "SUCCEEDED", "created_at": created,
                "report_summary": report, "versions": {"catalog": "demo-v1"}, "checksums": {"result": "sha256:demo"}}
    runs = [run("full-a", "FULL_ANALYSIS", "2026-09-26T10:00:00Z", summary("cap-a", "Приёмка", 3, "FULL", "200.00", "90.00")),
            run("partial-a", "FULL_ANALYSIS", "2026-09-25T10:00:00Z", summary("cap-a", "Приёмка", 2, "PARTIAL", "100.00", editable=True)),
            run("cap-a", "CAPACITY_ANALYSIS", "2026-09-25T09:00:00Z", summary("cap-a", "Приёмка", 2, "PARTIAL")),
            run("cap-b", "CAPACITY_ANALYSIS", "2026-09-25T08:00:00Z", summary("cap-b", "Отгрузка", 7, "PARTIAL"))]
    partial = {**runs[1], "input_snapshot": {"capacity_run_id": "cap-a", "economics": {
        "schema_version": "economics-explicit-inputs-v4", "input_revision": "revision.mock", "horizon_years": 5}},
        "result_snapshot": {"schema_version": "economics-partial-result-v1", "run_id": "partial-a",
            "capacity_run_id": "cap-a", "branches": {"capacity": {"status": "AVAILABLE", "selected_fleet": 2},
                "labour": {"status": "NOT_CALCULATED"}, "purchase": {"status": "NOT_CALCULATED"},
                "raas": {"status": "NOT_CALCULATED"}}, "scenarios": [], "c05": {"eligibility": "NEEDS_VALIDATION"}}}
    capacity = {**runs[2], "input_snapshot": {"process": {"role_refs": [], "scope": "TRANSPORT"}},
                "result_snapshot": {"schema_version": "capacity-analysis-response-v1"}}
    return project, runs, {"partial-a": partial, "cap-a": capacity}


def main():
    if not (DIST / "index.html").is_file() or not CHROME.is_file():
        raise RuntimeError("Build frontend and install Chrome first")
    project, runs, details = fixture()
    mock = """(() => { const project=%s, runs=%s, details=%s;
      window.__stage10mock=true;window.__stage10calls=[];
      window.fetch=(input)=>{const path=new URL(String(input),location.href).pathname;window.__stage10calls.push(path);
        let data=null;
        if(path==='/api/auth/me')data={user:{id:'owner-a',name:'Владелец',email:'owner@example.com'}};
        else if(path==='/api/projects')data={items:[project]};
        else if(path.endsWith('/analysis-runs'))data={items:runs};
        else if(path.includes('/analysis-runs/'))data=details[path.split('/').at(-1)];
        return Promise.resolve(new Response(JSON.stringify(data||{}),{status:data?200:404,
          headers:{'Content-Type':'application/json'}}));};
    })();""" % (json.dumps(project, ensure_ascii=False), json.dumps(runs, ensure_ascii=False), json.dumps(details, ensure_ascii=False))
    QuietHandler.injected_script = mock
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(DIST)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    profile = Path(tempfile.mkdtemp(prefix="stage10-chrome-", dir=ROOT))
    chrome = subprocess.Popen([str(CHROME), "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--remote-allow-origins=*", "--remote-debugging-port=0",
        f"--user-data-dir={profile}", "about:blank"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    seq = 0

    def call(method, params=None):
        nonlocal seq
        seq += 1
        ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            response = json.loads(ws.recv())
            if response.get("id") == seq:
                if response.get("error"):
                    raise RuntimeError(response["error"])
                return response.get("result", {})

    def js(source):
        result = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def until(source):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = js(source)
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(f"Timeout: {source}; mock={js('window.__stage10mock')}; calls={js('window.__stage10calls')}; body={js('document.body.innerText.slice(0,900)')}")

    try:
        active = profile / "DevToolsActivePort"
        for _ in range(100):
            if active.exists():
                break
            time.sleep(.1)
        if not active.exists():
            raise RuntimeError("Chrome DevTools did not start")
        port = active.read_text(encoding="utf-8").splitlines()[0]
        pages = json.load(urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3))
        ws = websocket.create_connection(next(page["webSocketDebuggerUrl"] for page in pages if page["type"] == "page"), timeout=5)
        web = f"http://127.0.0.1:{server.server_port}"
        call("Emulation.setDeviceMetricsOverride", {"width": 1366, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": f"{web}/#reports"})
        until("document.querySelectorAll('.reports-card').length===4")
        assert js("document.querySelectorAll('.reports-group').length") == 2
        assert js("document.body.innerText.includes('Частичный') && document.body.innerText.includes('Полный')")
        assert js("document.querySelector('.app-nav [aria-current=page]').innerText") == "Отчёт"
        assert js("[...document.querySelectorAll('.reports-card')].find(x=>x.querySelector('.reports-type')?.textContent.trim()==='Частичный')?.querySelector('.reports-npv')?.textContent.includes('не рассчитано')")
        assert js("(() => {const a=document.querySelectorAll('.reports-group')[0].querySelectorAll('input[type=checkbox]');a[0].click();a[1].click();return true})()")
        until("Boolean(document.querySelector('.reports-comparison'))")
        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        call("Page.reload", {"ignoreCache": True})
        until("document.querySelectorAll('.reports-card').length===4")
        bounds = js("(() => {const e=document.querySelector('.reports-screen');return [innerWidth,e.getBoundingClientRect().left,e.getBoundingClientRect().right,document.documentElement.scrollWidth]})()")
        assert bounds[0] == 390 and bounds[1] >= 0 and bounds[2] <= 391 and bounds[3] <= 391, bounds
        assert js("(() => {const b=[...document.querySelectorAll('.reports-card button')].find(x=>x.innerText==='Новая версия');b.click();return true})()")
        until("Boolean(document.querySelector('#edit-economics-run[open]'))")
        print("Reports route, partial/full cards, comparison, edit link and 390 px layout OK")
    finally:
        if ws is not None:
            ws.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
            chrome.wait(timeout=5)
        server.shutdown()
        server.server_close()
        if profile.resolve().is_relative_to(ROOT.resolve()) and profile.name.startswith("stage10-chrome-"):
            shutil.rmtree(profile)


if __name__ == "__main__":
    main()
