"""Live localhost stage 11 acceptance against a disposable stage11_* PostgreSQL."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import psycopg
import requests
import websocket
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:5173"
DB = os.getenv("DATABASE_URL", "")
if "127.0.0.1" not in DB or "/stage11_" not in DB:
    raise SystemExit("Stage 11 browser acceptance requires a disposable localhost stage11_* database")


def main() -> None:
    with psycopg.connect(DB.replace("postgresql+psycopg://", "postgresql://")) as connection:
        email = connection.execute("SELECT email_normalized FROM users WHERE email_normalized LIKE 'stage31-%' ORDER BY created_at DESC LIMIT 1").fetchone()[0]
    owner = requests.Session()
    login = owner.post(f"{API}/api/auth/login", json={"email": email, "password": "Stage31-local-only-2026"}, timeout=15)
    assert login.status_code == 200, login.text
    csrf = login.json()["csrf_token"]
    project = next(item for item in owner.get(f"{API}/api/projects", timeout=15).json()["items"] if "одноразовый склад" in item["name"])
    pid = project["id"]
    history = owner.get(f"{API}/api/projects/{pid}/analysis-runs", timeout=20).json()["items"]
    assert len(history) >= 3
    full = next(item for item in history if item["report_summary"]["result_type"] == "FULL")
    partial = next(item for item in history if item["report_summary"]["result_type"] == "PARTIAL" and item["run_kind"] == "FULL_ANALYSIS")
    assert not partial["report_summary"]["npv"]
    source = owner.get(f"{API}/api/projects/{pid}/analysis-runs/{full['id']}", timeout=20).json()
    base = f"{API}/api/projects/{pid}/analysis-runs/{full['id']}/exports"
    manifest = owner.get(f"{base}/manifest", timeout=20).json()
    pdf = owner.get(f"{base}/report.pdf", timeout=25)
    archive = owner.get(f"{base}/evidence.zip", timeout=25)
    assert pdf.status_code == archive.status_code == 200
    assert pdf.headers["X-Report-Source-Digest"] == manifest["source_snapshot_digests"]["result"] == "sha256:" + source["checksums"]["result"]
    assert archive.headers["X-Export-Manifest-Digest"] == manifest["manifest_digest"]
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert bundle.testzip() is None
        assert json.loads(bundle.read("manifest.json")) == manifest
        assert bundle.read(manifest["report_filename"]) == pdf.content
        for artifact in manifest["artifacts"]:
            assert artifact["sha256"] == "sha256:" + hashlib.sha256(bundle.read(artifact["filename"])).hexdigest()
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "После покупки роботов" in pdf_text and "При аренде роботов" in pdf_text
    assert owner.get(f"{API}/api/projects/{pid}/analysis-runs/{full['id']}", timeout=20).json()["checksums"] == source["checksums"]
    stranger = requests.Session()
    other = stranger.post(f"{API}/api/auth/register", json={"email": f"stage11-{time.time_ns()}@example.com", "password": "Stage11-local-only-2026"}, timeout=15)
    assert other.status_code == 201
    assert stranger.get(f"{API}/api/projects/{pid}/analysis-runs", timeout=15).status_code == 404
    assert stranger.get(f"{base}/report.pdf", timeout=15).status_code == 404
    catalog = owner.get(f"{API}/api/roboexpert/options", timeout=15).json()
    web = owner.post(f"{API}/api/roboexpert/web", json={"position_id": catalog["items"][0]["position_id"],
        "catalog_version": catalog["catalog_version"], "topic": "passport"},
        headers={"X-CSRF-Token": csrf}, timeout=15)
    assert web.status_code == 200, web.text
    assert web.json()["status"] == "unavailable" and web.json()["results"] == []
    assert owner.get(f"{API}/api/projects/{pid}/analysis-runs/{full['id']}", timeout=20).json()["checksums"] == source["checksums"]
    print("PASS: live owner history, immutable PDF/ZIP digest and tenant isolation", flush=True)

    profile = Path(tempfile.mkdtemp(prefix="stage11-chrome-", dir=ROOT / ".tmp"))
    chrome = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new",
        "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
        "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    seq = 0
    console_warnings = []

    def call(method, params=None):
        nonlocal seq
        seq += 1
        ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            value = json.loads(ws.recv())
            if value.get("method") == "Runtime.consoleAPICalled" and value.get("params", {}).get("type") in {"warning", "error"}:
                message = " ".join(str(item.get("value") or item.get("description") or "") for item in value["params"].get("args", []))
                console_warnings.append(message)
            if value.get("id") == seq:
                if value.get("error"):
                    raise RuntimeError(value["error"])
                return value.get("result", {})

    def js(source):
        result = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def until(source, seconds=25):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = js(source)
            if value:
                return value
            time.sleep(.2)
        raise AssertionError(f"Timeout: {source}; url={js('location.href')}; page={js('document.body.innerText.slice(0,1100)')}; alerts={js('[...document.querySelectorAll(\"[role=alert]\")].map(e=>e.textContent)')}")

    try:
        active = profile / "DevToolsActivePort"
        for _ in range(80):
            if active.exists():
                break
            time.sleep(.2)
        assert active.exists()
        port = active.read_text().splitlines()[0]
        pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=3).json()
        ws = websocket.create_connection(next(item["webSocketDebuggerUrl"] for item in pages if item["type"] == "page"), timeout=5)
        call("Runtime.enable")
        for cookie in owner.cookies:
            call("Network.setCookie", {"name": cookie.name, "value": cookie.value, "url": WEB})
        for width in (1366, 390):
            call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 844, "deviceScaleFactor": 1, "mobile": width == 390})
            call("Page.navigate", {"url": "about:blank"})
            until("location.href === 'about:blank'")
            call("Page.navigate", {"url": f"{WEB}/#reports"})
            until("document.querySelectorAll('.reports-card').length >= 3")
            assert js("document.body.innerText.includes('Частичный') && document.body.innerText.includes('Полный')")
            assert js("document.documentElement.scrollWidth <= innerWidth + 1"), (width, js("document.documentElement.scrollWidth"))
            assert js("""(() => {const text=getComputedStyle(document.querySelector('.reports-card-top time')).color;
              const background=getComputedStyle(document.querySelector('.reports-card')).backgroundColor;
              const luminance=(value)=>{const rgb=value.match(/[\\d.]+/g).slice(0,3).map(Number).map(x=>x/255)
                .map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]};
              const a=luminance(text),b=luminance(background);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5})()""")
            assert js("(() => {const g=[...document.querySelectorAll('.reports-group')].find(g=>g.querySelectorAll('input[type=checkbox]').length>=2);if(!g)return false;g.querySelectorAll('input[type=checkbox]')[0].click();return true})()")
            until("document.querySelector('.reports-group input[type=checkbox]:checked') !== null")
            assert js("(() => {const g=[...document.querySelectorAll('.reports-group')].find(g=>g.querySelectorAll('input[type=checkbox]').length>=2);g.querySelectorAll('input[type=checkbox]')[1].click();return true})()")
            until("Boolean(document.querySelector('.reports-comparison'))")
            print(f"PASS: live reports and comparison at {width}px", flush=True)
        call("Page.navigate", {"url": f"{WEB}/#roboexpert"})
        until("document.querySelectorAll('.roboexpert-option input[type=checkbox]').length >= 2")
        assert js("(() => {const x=[...document.querySelectorAll('.roboexpert-option input[type=checkbox]')];x[0].click();const y=x.find(e=>e!==x[0]&&!e.disabled);if(!y)return false;y.click();return true})()")
        assert js("[...document.querySelectorAll('.roboexpert-card button')].find(e=>e.textContent.includes('Сравнить выбранные'))?.disabled === false")
        assert js("(() => {const e=[...document.querySelectorAll('.roboexpert-card button')].find(e=>e.textContent.includes('Сравнить выбранные'));e.click();return true})()")
        until("Boolean(document.querySelector('[aria-label=\"Структурированное сравнение\"]'))")
        assert js("document.body.innerText.includes('Информационные решения каталога')")
        assert js("(() => {const e=[...document.querySelectorAll('.roboexpert-research button')].find(e=>e.textContent.includes('Составить пояснение'));e?.click();return Boolean(e)})()")
        until("document.querySelector('.roboexpert-external')?.textContent.includes('AI Studio не настроен')")
        assert js("document.querySelector('[aria-label=\"Структурированное сравнение\"]') !== null")
        assert js("document.documentElement.scrollWidth <= innerWidth + 1")
        print("PASS: live Roboexpert comparison remains usable without AI Studio", flush=True)
        call("Page.navigate", {"url": f"{WEB}/#reports"})
        until("document.querySelectorAll('.reports-card').length >= 3")
        assert js("(() => {const e=[...document.querySelectorAll('.reports-card')].find(e=>e.querySelector('.reports-type')?.textContent.trim()==='Полный');e?.querySelector('.reports-actions button')?.click();return Boolean(e)})()")
        until("Boolean(document.querySelector('.commercial-screen'))")
        until("Boolean(document.querySelector('.simulation-kpis'))", 90)
        assert js("Boolean(document.querySelector('.warehouse-2d-plan') || document.querySelector('.simulation-canvas-wrap svg'))")
        assert js("(() => {const tab=[...document.querySelectorAll('[role=tab]')].find(e=>e.textContent.trim()==='3D');tab?.click();return Boolean(tab)})()")
        until("Boolean(document.querySelector('.robcraft-frame iframe'))")
        until("document.querySelector('.robcraft-frame iframe')?.contentDocument?.readyState === 'complete'", 30)
        assert js("document.documentElement.scrollWidth <= innerWidth + 1")
        call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
        call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
        assert js("document.activeElement !== document.body && document.activeElement !== null")
        call("Page.navigate", {"url": f"{WEB}/#reports"})
        until("document.querySelectorAll('.reports-card').length >= 3")
        js("history.back()")
        until("Boolean(document.querySelector('.commercial-screen'))")
        assert not [item for item in console_warnings if "key" in item.lower()], console_warnings
        print("PASS: saved full result reopens 2D/3D on mobile; keyboard focus and Back work", flush=True)
    finally:
        if ws is not None:
            ws.close()
        chrome.terminate()
        chrome.wait(timeout=10)
        if profile.resolve().is_relative_to(ROOT.resolve()) and profile.name.startswith("stage11-chrome-"):
            for attempt in range(5):
                try:
                    shutil.rmtree(profile)
                    break
                except PermissionError:
                    if attempt == 4:
                        print(f"Temporary Chrome cache could not be removed: {profile}", flush=True)
                    else:
                        time.sleep(.4)


if __name__ == "__main__":
    main()
