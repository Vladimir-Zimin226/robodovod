"""F5 browser/API acceptance on new runs in a disposable local database."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
import zipfile
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/planning/assets/f5/evidence"
OUT.mkdir(parents=True, exist_ok=True)
database_url = os.environ["F5_DATABASE_URL"].replace("postgresql+psycopg:", "postgresql:")
parsed = urlparse(database_url)
assert (parsed.hostname, parsed.port, parsed.path) == (
    "127.0.0.1", 5541, "/stage11_f1_browser"
)
api, web = "http://127.0.0.1:8000", "http://127.0.0.1:5173"
with psycopg.connect(database_url) as db:
    email = db.execute("SELECT email_normalized FROM users WHERE email_normalized LIKE 'stage31-%' ORDER BY created_at DESC LIMIT 1").fetchone()[0]
    before = {
        name: {str(row[0]): row[1] for row in db.execute(f"SELECT id,row_to_json(r) FROM {name} r")}
        for name in ("analysis_runs", "simulation_artifacts", "catalog_versions")
    }
owner = requests.Session()
login = owner.post(f"{api}/api/auth/login", json={"email": email, "password": "Stage31-local-only-2026"}, timeout=10)
assert login.ok, login.text
project = next(item for item in owner.get(f"{api}/api/projects", timeout=10).json()["items"]
               if "одноразовый склад" in item["name"])
project_id = project["id"]
base = f"{api}/api/projects/{project_id}/analysis-runs"
history = owner.get(base, timeout=10).json()["items"]
runs = [owner.get(f"{base}/{item['id']}", timeout=10).json() for item in history
        if item["run_kind"] == "FULL_ANALYSIS"]
run = next((item for item in runs if item["result_snapshot"].get("schema_version") == "commercial-scenarios-bundle-v3"), None)
if run is None:
    source = next(item for item in runs if item["result_snapshot"].get("schema_version") == "commercial-scenarios-bundle-v2")
    partial = next(item for item in runs if item["result_snapshot"].get("schema_version") == "economics-partial-result-v1")
    capacity_id = partial["input_snapshot"]["capacity_run_id"]
    capacity = owner.get(f"{base}/{capacity_id}", timeout=10).json()
    economics = deepcopy(source["input_snapshot"]["economics"])
    economics["input_revision"] = capacity["input_snapshot"]["input_revision"]
    response = owner.post(f"{api}/api/v2/projects/{project_id}/economics-runs",
        headers={"X-CSRF-Token": login.json()["csrf_token"]}, timeout=60,
        json={"scenario_id": next(s["id"] for s in project["scenarios"] if s["slot"] == "BASE"),
              "capacity_run_id": capacity_id,
              "source_run_id": partial["id"], "input": economics})
    assert response.status_code == 201, response.text
    run = response.json()
assert run["result_snapshot"]["schema_version"] == "commercial-scenarios-bundle-v3"
run_id = run["id"]
simulation_base = f"{api}/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}"
saved = owner.get(f"{simulation_base}/evidence", timeout=15).json()["items"]
if not saved:
    spec = run["scenario_spec_snapshot"]
    primary = next((window for window in spec["operating_windows"] if window["window_id"] == "window.primary"),
                   spec["operating_windows"][0])
    request = {"schema_version": "simulation-request-v2", "request_id": f"simulation.f5.{run_id}",
        "tenant_id": spec["analysis"]["tenant_id"], "project_id": project_id,
        "scenario_spec": spec, "mode": "DAILY", "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100,
                   "max_runtime_seconds": 60, "progress_event_batch": 1000},
        "model_start": {"weekday": "MONDAY", "seconds_from_midnight": int(primary["start_time"]["value"]),
                        "timezone": primary["timezone"]}, "process_chain": None}
    started = owner.post(simulation_base, json=request,
        headers={"X-CSRF-Token": login.json()["csrf_token"]}, timeout=20)
    assert started.status_code == 202, started.text
    for _ in range(240):
        state = owner.get(f"{simulation_base}/{request['request_id']}", timeout=10).json()
        if state["state"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(.1)
    assert state["state"] == "SUCCEEDED", state
export_base = f"{base}/{run_id}/exports"
manifest = owner.get(f"{export_base}/manifest", timeout=30).json()
archive = owner.get(f"{export_base}/evidence.zip", timeout=30)
pdf = owner.get(f"{export_base}/report.pdf", timeout=30)
xlsx = owner.get(f"{export_base}/result.xlsx", timeout=30)
csv = owner.get(f"{export_base}/comparison.csv", timeout=30)
svg = owner.get(f"{export_base}/visualization.svg", timeout=30)
assert all(response.ok for response in (archive, pdf, xlsx, csv, svg))
assert manifest["schema_version"] == "calculation-evidence-export-manifest-v4"
assert manifest["simulation_request_id"] and manifest["simulation_report_digest"]
with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
    for artifact in manifest["artifacts"]:
        assert artifact["sha256"] == "sha256:" + hashlib.sha256(package.read(artifact["filename"])).hexdigest()
    for name, response in (("Отчёт_Рободовод.pdf", pdf), ("Результат.xlsx", xlsx),
                           ("Сравнение.csv", csv), ("Схема_2D.svg", svg)):
        assert package.read(name) == response.content
assert csv.content.startswith(b"\xef\xbb\xbf")

profile = Path(tempfile.mkdtemp(prefix="f5-chrome-", dir=ROOT / ".tmp"))
chrome = subprocess.Popen([
    r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new",
    "--no-first-run", "--remote-allow-origins=*", "--remote-debugging-port=0",
    "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    f"--user-data-dir={profile}", "about:blank",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
ws = None
seq = 0
errors = []


def call(method: str, params: dict | None = None) -> dict:
    global seq
    seq += 1
    ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
    while True:
        message = json.loads(ws.recv())
        if message.get("method") == "Runtime.exceptionThrown":
            errors.append(message["params"])
        if message.get("id") == seq:
            assert not message.get("error"), message
            return message.get("result", {})


def js(source: str):
    response = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
    assert not response.get("exceptionDetails"), response
    return response.get("result", {}).get("value")


def until(source: str):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            value = js(source)
        except AssertionError as exc:
            if "Inspected target navigated or closed" not in str(exc):
                raise
            time.sleep(.2)
            continue
        if value:
            return value
        time.sleep(.2)
    raise AssertionError(f"Timeout: {source}; page={js('document.body.innerText.slice(-1200)')}")


screens = []
try:
    deadline = time.monotonic() + 20
    while not (profile / "DevToolsActivePort").exists():
        assert time.monotonic() < deadline
        time.sleep(.1)
    port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
    ws = websocket.create_connection(next(page["webSocketDebuggerUrl"] for page in pages if page["type"] == "page"), timeout=15)
    call("Runtime.enable")
    call("Page.enable")
    call("Network.enable")
    for cookie in owner.cookies:
        call("Network.setCookie", {"name": cookie.name, "value": cookie.value, "url": web})
    for width, height in ((1366, 768), (390, 844)):
        call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height,
            "deviceScaleFactor": 1, "mobile": width == 390})
        call("Page.navigate", {"url": f"{web}/#reports"})
        until(f"[...document.querySelectorAll('.reports-card')].some(card => card.textContent.includes({json.dumps(run_id)}))")
        assert js(f"(() => {{const card=[...document.querySelectorAll('.reports-card')].find(x=>x.textContent.includes({json.dumps(run_id)}));const buttons=[...card.querySelectorAll('.reports-actions button')].map(x=>x.textContent.trim());return ['PDF','XLSX','CSV'].every(x=>buttons.includes(x))}})()")
        js(f"[...document.querySelectorAll('.reports-card')].find(x=>x.textContent.includes({json.dumps(run_id)})).querySelector('.reports-actions button').click()")
        until("document.querySelector('[aria-label=\"Полное сравнение экономики\"] table tbody tr') !== null")
        assert js("document.querySelector('[aria-label=\"Полное сравнение экономики\"] table tbody').rows.length") == 12
        assert js("document.querySelector('[aria-label=\"Полное сравнение экономики\"]').textContent.includes('Baseline, покупка и услуга')")
        until("document.querySelector('.evidence-export-v2 button') !== null")
        until("document.querySelector('.evidence-export-v2').textContent.includes('Скачать XLSX')")
        assert js("document.documentElement.scrollWidth <= innerWidth + 1"), width
        js("document.querySelector('[aria-label=\"Полное сравнение экономики\"]').scrollIntoView({block:'start',behavior:'instant'})")
        time.sleep(.5)
        path = OUT / f"comparison-{width}.png"
        path.write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
        screens.append(str(path.relative_to(ROOT)))
    assert not errors, errors
finally:
    if ws:
        ws.close()
    chrome.terminate()
    chrome.wait(timeout=10)
with psycopg.connect(database_url) as db:
    after = {
        name: {str(row[0]): row[1] for row in db.execute(f"SELECT id,row_to_json(r) FROM {name} r")}
        for name in before
    }
assert all({key: after[name].get(key) for key in rows} == rows for name, rows in before.items()), (
    "F5 calculation or read-only exports altered historical rows"
)
(OUT / "report.json").write_text(json.dumps({
    "run_id": run_id, "result_digest": manifest["source_snapshot_digests"]["result"],
    "manifest_digest": manifest["manifest_digest"],
    "simulation_request_id": manifest["simulation_request_id"],
    "historical_runs_unchanged": len(before["analysis_runs"]),
    "historical_artifacts_unchanged": len(before["simulation_artifacts"]),
    "screenshots": screens,
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"PASS F5 browser: {run_id}, desktop/mobile, direct files and {len(before['analysis_runs'])} unchanged runs")
