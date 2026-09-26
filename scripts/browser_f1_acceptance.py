"""F1 acceptance on disposable localhost services, after browser_stage31_brain.py.

F1_DATABASE_URL must identify the disposable stage11_* database used by backend.
No production reads/writes; artifacts go to .tmp/f1/acceptance.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
import uuid
import zipfile
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import psycopg
import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
API, WEB = "http://127.0.0.1:8000", "http://127.0.0.1:5173"
OUT = ROOT / (".tmp/f3/physical" if os.getenv("F1_ACCEPTANCE_STAGE") == "F3" else ".tmp/f1/acceptance")
OUT.mkdir(parents=True, exist_ok=True)
url = os.environ["F1_DATABASE_URL"].replace("postgresql+psycopg:", "postgresql:")
parsed = urlparse(url)
assert parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path.startswith("/stage11_")
with psycopg.connect(url) as db:
    email = db.execute("SELECT email_normalized FROM users WHERE email_normalized LIKE 'stage31-%' ORDER BY created_at DESC LIMIT 1").fetchone()[0]
owner = requests.Session()
login = owner.post(f"{API}/api/auth/login", json={"email": email, "password": "Stage31-local-only-2026"}, timeout=10)
assert login.ok
headers = {"X-CSRF-Token": login.json()["csrf_token"]}
project = next(p for p in owner.get(f"{API}/api/projects", timeout=10).json()["items"] if "одноразовый склад" in p["name"])
pid = project["id"]
base = f"{API}/api/projects/{pid}/analysis-runs"


def get_run(rid):
    response = owner.get(f"{base}/{rid}", timeout=20)
    assert response.ok, response.text
    return response.json()


history = owner.get(base, timeout=10).json()["items"]
runs = [get_run(row["id"]) for row in history if row["run_kind"] == "FULL_ANALYSIS"]
if os.getenv("F1_ACCEPTANCE_STAGE") == "F3":
    runs.sort(key=lambda run: run["versions"]["catalog"] != "organizer-catalog-v4")
small = next(run for run in runs if run["scenario_spec_snapshot"]["tasks"][0]["demand"]["value"] == "220"
             and run["scenario_spec_snapshot"]["routes"][0]["one_way_distance"]["value"] == "120")
typical = next(run for run in runs if run["result_snapshot"]["schema_version"] == "commercial-scenarios-bundle-v2")
originals = {run["id"]: deepcopy(run) for run in (small, typical)}
pdfs = {rid: owner.get(f"{base}/{rid}/exports/report.pdf", timeout=30).content for rid in originals}


def sim_request(run):
    spec = run["scenario_spec_snapshot"]
    primary = next((w for w in spec["operating_windows"] if w["window_id"] == "window.primary"), spec["operating_windows"][0])
    return {"schema_version": "simulation-request-v2", "request_id": f"simulation.{run['id']}.v2",
        "tenant_id": spec["analysis"]["tenant_id"], "project_id": pid, "scenario_spec": spec,
        "mode": "DAILY", "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100, "max_runtime_seconds": 60, "progress_event_batch": 1000},
        "model_start": {"weekday": "MONDAY", "seconds_from_midnight": int(primary["start_time"]["value"]), "timezone": primary["timezone"]},
        "process_chain": None}


def evidence(run):
    request = sim_request(run)
    sim = f"{API}/api/v2/simulations/projects/{pid}/analysis-runs/{run['id']}"
    response = owner.post(sim, json=request, headers=headers, timeout=20)
    assert response.status_code == 202, response.text
    for _ in range(240):
        state = owner.get(f"{sim}/{request['request_id']}", timeout=10).json()
        if state["state"] in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(.1)
    assert state["state"] == "SUCCEEDED", state
    data = owner.get(f"{sim}/{request['request_id']}/evidence.json", timeout=15).json()
    spec, report = data["request"]["scenario_spec"], data["report"]
    capacity = get_run(spec["analysis"]["capacity_run_id"])
    process = capacity["input_snapshot"]["process"]
    values = capacity["result_snapshot"]["capacity"]["value"]
    assert data["request"] == request and spec == run["scenario_spec_snapshot"]
    assert spec["tasks"][0]["demand"]["value"] == process["demand"]["normalized_value"]
    assert spec["routes"][0]["one_way_distance"]["value"] == process["route_distance"]["normalized_value"]
    assert spec["tasks"][0]["batch"]["units_per_cycle"]["value"] == process["explicit_batch"]["normalized_value"]
    fleet = spec["fleet"][0]
    assert (fleet["model_id"], fleet["position_id"]) == (capacity["input_snapshot"]["model_id"], capacity["input_snapshot"]["position_id"])
    assert fleet["selected_fleet"] == values["selected_fleet"] == report["workload"]["fleet_units"]
    assert fleet["effective_capacity"] == values["effective_capacity"]
    assert spec["profile"]["process_id"] == process["process_id"]
    hours = Decimal(process["schedule"]["shifts_per_day"]["normalized_value"]) * Decimal(process["schedule"]["shift_hours"]["normalized_value"])
    assert sum(Decimal(w["duration"]["value"]) for w in spec["operating_windows"]) == hours
    assert Decimal(report["capacity"]["required_per_hour"]) * hours == Decimal(process["demand"]["normalized_value"])
    assert report["model_start"] == request["model_start"]
    assert data["scenario_spec_digest"] == "sha256:" + run["checksums"]["scenario_spec"]
    archive = owner.get(f"{base}/{run['id']}/exports/evidence.zip", timeout=30)
    assert archive.ok
    with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["source_snapshot_digests"]["scenario_spec"] == data["scenario_spec_digest"]
        for artifact in manifest["artifacts"]:
            assert artifact["sha256"] == "sha256:" + hashlib.sha256(package.read(artifact["filename"])).hexdigest()
    return data


saved = {run["id"]: evidence(run) for run in (small, typical)}
# Create separate saved versions for changes of each physical input.
new_runs = []
for field, value in [("demand", "260"), ("route_distance", "180"), ("selected_fleet", "1")]:
    source = typical if field == "selected_fleet" else small
    raw = deepcopy(get_run(source["input_snapshot"]["capacity_run_id"])["input_snapshot"])
    revision = f"revision.f1.{uuid.uuid4().hex}"
    raw["input_revision"] = raw["process"]["input_revision"] = revision
    for provenance in raw["provenance"]:
        if "confirmation_revision" in provenance:
            provenance["confirmation_revision"] = revision
    if field == "selected_fleet":
        raw["provenance"].append({"kind": "USER", "provenance_id": "prov.f1.fleet", "confirmation_revision": revision})
        raw[field] = {"name": "fleet_selected", "raw_value": value, "normalized_value": value,
                      "raw_unit": "robot", "unit": "robot", "quantity_kind": "COUNT", "provenance_ref": "prov.f1.fleet"}
    else:
        raw["process"][field]["raw_value"] = raw["process"][field]["normalized_value"] = value
    response = owner.post(f"{API}/api/v2/capacity-analyses", json=raw, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    response = owner.post(f"{API}/api/v2/projects/{pid}/economics-runs", headers=headers, timeout=30,
        json={"scenario_id": next(s["id"] for s in project["scenarios"] if s["slot"] == "BASE"),
              "capacity_run_id": response.json()["run_id"], "source_run_id": source["id"],
              "input": {"schema_version": "economics-explicit-inputs-v4", "input_revision": revision,
                        "start_seconds_from_midnight": "32400", "timezone": "Asia/Sakhalin"}})
    assert response.status_code == 201, response.text
    new = response.json(); new_runs.append(new)
    saved[new["id"]] = evidence(new)
    assert new["scenario_spec_snapshot"]["revision_id"] != source["scenario_spec_snapshot"]["revision_id"]
overloaded = saved[new_runs[-1]["id"]]["report"]
assert overloaded["capacity"]["verdict"] == "OVERLOADED" and overloaded["queue"]["maximum_jobs"] > 0
# Valid, but belonging to another run: exact-spec gate rejects it.
sim_base = f"{API}/api/v2/simulations/projects/{pid}/analysis-runs/{small['id']}"
assert owner.post(sim_base, headers=headers, json=sim_request(new_runs[0]), timeout=15).status_code == 409
stranger = requests.Session()
assert stranger.post(f"{API}/api/auth/register", json={"email": f"f1-{uuid.uuid4().hex}@example.com", "password": "F1-local-test-password"}, timeout=10).status_code == 201
assert stranger.get(base, timeout=10).status_code == 404
assert stranger.get(f"{sim_base}/{sim_request(small)['request_id']}/evidence.json", timeout=10).status_code == 404
assert stranger.get(f"{base}/{small['id']}/exports/report.pdf", timeout=15).status_code == 404
print("PASS: API physical inputs, three new versions, foreign spec 409, owner isolation, overload and manifest", flush=True)

profile = Path(tempfile.mkdtemp(prefix="chrome-", dir=OUT))
chrome = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new",
    "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*", "--remote-debugging-port=0",
    "--use-angle=swiftshader", "--enable-unsafe-swiftshader", f"--user-data-dir={profile}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
ws, seq = None, 0
warnings = []


def call(method, params=None):
    global seq
    seq += 1; ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get("method") == "Runtime.consoleAPICalled" and result["params"]["type"] in {"error", "warning"}:
            warnings.append(str(result["params"]["args"]))
        if result.get("id") == seq:
            assert not result.get("error"), result
            return result.get("result", {})


def js(source):
    result = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
    assert not result.get("exceptionDetails"), result
    return result.get("result", {}).get("value")


def until(source):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            result = js(source)
        except AssertionError as error:
            if "Inspected target navigated or closed" not in str(error):
                raise
            time.sleep(.15)
            continue
        if result:
            return result
        time.sleep(.15)
    raise AssertionError(f"Timeout: {source}; page={js('document.body.innerText.slice(-1800)')}")


def button(text, selector=".simulation-2d button"):
    assert js(f"(() => {{const e=[...document.querySelectorAll({json.dumps(selector)})].find(x=>x.textContent.trim()==={json.dumps(text)});if(!e)return false;e.click();return true}})()")


def select_run(run):
    rid = run["id"]
    until(f"[...document.querySelector('[aria-label=\"Физический сценарий проекта\"]')?.options || []].some(x=>x.value === {json.dumps(rid)})")
    assert js(f"(() => {{const e=document.querySelector('[aria-label=\"Физический сценарий проекта\"]');e.value={json.dumps(rid)};e.dispatchEvent(new Event('change',{{bubbles:true}}));return e.value}})()") == rid
    until(f"document.querySelector('.simulation-bindings')?.textContent.includes({json.dumps(rid)})")
    until(f"document.querySelector('iframe')?.contentWindow.__f1Loads?.at(-1)?.payload.simulation_report.report_id === {json.dumps(saved[rid]['report']['report_id'])}")
    loaded = js("document.querySelector('iframe').contentWindow.__f1Loads.at(-1).payload")
    assert loaded["scenario_spec"] == saved[rid]["request"]["scenario_spec"]
    assert loaded["simulation_report"] == saved[rid]["report"]


try:
    for _ in range(100):
        if (profile / "DevToolsActivePort").exists(): break
        time.sleep(.1)
    port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
    ws = websocket.create_connection(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"), timeout=10)
    call("Runtime.enable"); call("Page.enable")
    call("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(OUT)})
    call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__f1Loads=[];addEventListener('message',e=>{if(e.data?.type==='LOAD_SCENARIO')window.__f1Loads.push(e.data);if(e.data?.type==='SET_PLAYBACK')window.__f1Playback=e.data.payload});const old=URL.createObjectURL;URL.createObjectURL=b=>{window.__f1Blob=b;return old(b)};"})
    for cookie in owner.cookies:
        call("Network.setCookie", {"name": cookie.name, "value": cookie.value, "url": WEB})
    for width, height in [(1366, 768), (390, 844)]:
        call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width == 390})
        call("Page.navigate", {"url": f"{WEB}/#reports"})
        until("document.querySelectorAll('.reports-card').length > 0")
        assert js(f"(() => {{const card=[...document.querySelectorAll('.reports-card')].find(x=>x.textContent.includes({json.dumps(typical['id'])}));card.querySelector('.reports-actions button').click();return true}})()")
        until("document.querySelector('[aria-label=\"Физический сценарий проекта\"]')?.options.length >= 5")
        for run in [typical, small, new_runs[-1], small]:
            select_run(run)
            button("Пауза"); until("document.querySelector('.simulation-controls strong').textContent === 'Пауза'")
            assert js("document.querySelector('[aria-label=\"Условная зарядная точка\"]') !== null")
            if run == new_runs[-1]:
                assert js("document.querySelector('.simulation-warning').textContent.includes('Спрос превышает')")
            button("Сохранить открытый 2D-кадр · SVG")
            svg = until("window.__f1Blob?.text()")
            doc = ET.fromstring(svg); meta = json.loads(doc.find('{http://www.w3.org/2000/svg}metadata').text)
            assert meta["request"] == saved[run["id"]]["request"] and meta["report"] == saved[run["id"]]["report"]
            assert meta["analysis_run_id"] == run["id"]
            assert not any('href' in attribute for node in doc.iter() for attribute in node.attrib)
            (OUT / f"{width}-{run['id']}.svg").write_text(svg, encoding="utf-8")
            button("3D", '.simulation-view-tabs button'); until("document.querySelector('[role=tab][aria-selected=true]').textContent === '3D'")
            button("2D", '.simulation-view-tabs button')
        button("Стоп"); until("document.querySelector('.simulation-controls strong').textContent === 'Остановлено'")
        button("Перезапуск"); until("document.querySelector('.simulation-controls strong').textContent === 'Воспроизведение'")
        js("(() => {const e=document.querySelector('.simulation-controls select');e.value='4';e.dispatchEvent(new Event('change',{bubbles:true}))})()")
        assert js("document.querySelector('.simulation-controls select').value") == '4'
        until("document.querySelector('iframe').contentWindow.__f1Playback?.speed === 4")
        button("Пауза"); button("Старт"); button("Пауза")
        assert js("document.documentElement.scrollWidth <= innerWidth + 1"), width
        (OUT / f"{width}.png").write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        call("Page.navigate", {"url": f"{WEB}/#reports"}); until("document.querySelectorAll('.reports-card').length > 0")
        js("history.back()"); until("document.querySelector('.simulation-bindings') !== null")
        select_run(small)
        call("Page.reload"); until("document.querySelector('.simulation-bindings') === null")
        call("Page.navigate", {"url": f"{WEB}/#reports"}); until("document.querySelectorAll('.reports-card').length > 0")
        js(f"[...document.querySelectorAll('.reports-card')].find(x=>x.textContent.includes({json.dumps(small['id'])})).querySelector('.reports-actions button').click()")
        until("document.querySelector('.simulation-bindings') !== null"); select_run(small)
        call("Page.navigate", {"url": (OUT / f"{width}-{small['id']}.svg").as_uri()})
        until("document.querySelector('svg metadata') !== null")
        assert js("document.querySelector('svg').textContent.includes('Зарядка учтена агрегированно')")
        (OUT / f"{width}-standalone.png").write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        print(f"PASS: {width}x{height} physical selector, C23 -> 3D equality, controls, Back/reload, SVG standalone", flush=True)
    # Changing the project clears the old result before Back can display it.
    response = owner.post(f"{API}/api/projects", headers=headers, json={"name": f"F1 empty {uuid.uuid4().hex[:8]}"}, timeout=10)
    assert response.status_code == 201
    empty = response.json()
    call("Page.navigate", {"url": f"{WEB}/#reports"}); until("document.querySelectorAll('.reports-card').length > 0")
    js(f"[...document.querySelectorAll('.reports-card')].find(x=>x.textContent.includes({json.dumps(small['id'])})).querySelector('.reports-actions button').click()")
    until("document.querySelector('.simulation-bindings') !== null")
    button("Мои проекты", '.nav-secondary button'); until("document.querySelectorAll('.project-card').length > 1")
    js(f"[...document.querySelectorAll('.project-card')].find(x=>x.textContent.includes({json.dumps(empty['name'])})).querySelector('.card-actions button').click()")
    until(f"document.querySelector('.project-context').textContent.includes({json.dumps(empty['name'])})")
    js("history.back()"); until("location.hash === '#projects'")
    js("history.back()"); until("document.querySelector('.simulation-bindings') === null")
    # Logout and another login in the same React session must not restore old runs.
    js("document.querySelector('.user-avatar').click()"); until("document.querySelector('.account-actions') !== null")
    button("Выйти", '.account-actions button'); until("document.querySelector('.user-avatar').title === 'Войти'")
    js("document.querySelector('.user-avatar').click()"); until("document.querySelector('.auth-screen') !== null")
    other_email = stranger.get(f"{API}/api/auth/me", timeout=10).json()["user"]["email"]
    for selector, value in [('input[type=email]', other_email), ('input[type=password]', 'F1-local-test-password')]:
        js(f"(() => {{const e=document.querySelector({json.dumps(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,{json.dumps(value)});e.dispatchEvent(new Event('input',{{bubbles:true}}))}})()")
    button("Войти", '.auth-screen button'); until("document.querySelector('.account-actions') !== null")
    js("history.back()"); until("document.querySelector('.simulation-bindings') === null")
    assert not js(f"document.body.textContent.includes({json.dumps(small['id'])})")
    print("PASS: project switch, Back, logout and different user clear the old simulation and 3D", flush=True)
    assert not warnings, warnings
finally:
    if ws: ws.close()
    chrome.terminate(); chrome.wait(timeout=10)
login = owner.post(f"{API}/api/auth/login", json={"email": email, "password": "Stage31-local-only-2026"}, timeout=10)
assert login.ok
headers = {"X-CSRF-Token": login.json()["csrf_token"]}
for rid, original in originals.items():
    assert get_run(rid)["checksums"] == original["checksums"]
    assert get_run(rid)["scenario_spec_snapshot"] == original["scenario_spec_snapshot"]
    assert owner.get(f"{base}/{rid}/exports/report.pdf", timeout=30).content == pdfs[rid]
    assert evidence(original) == saved[rid]
(OUT / "bindings.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
print("PASS: original runs, PDF bytes and saved C23 digests unchanged after new calculations and exports", flush=True)
