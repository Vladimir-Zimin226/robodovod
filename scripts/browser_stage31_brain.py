"""Stage 3.1 browser acceptance against disposable localhost services/DB only."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
MOBILE = os.getenv("STAGE31_MOBILE") == "1"
API = os.getenv("STAGE31_API", "http://127.0.0.1:8000")
WEB = os.getenv("STAGE31_WEB", "http://127.0.0.1:5173")
browser_profile = Path(tempfile.mkdtemp(prefix="stage31-chrome-", dir=ROOT / ".tmp"))
chrome = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new", "--disable-gpu",
    "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*", "--remote-debugging-port=0",
    f"--user-data-dir={browser_profile}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW)
ws = None
seq = 0
react_key_warnings = []


def call(method, params=None):
    global seq
    seq += 1
    ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
    while True:
        response = json.loads(ws.recv())
        if response.get("method") == "Runtime.consoleAPICalled":
            message = " ".join(str(item.get("value") or item.get("description") or "")
                               for item in response.get("params", {}).get("args", []))
            if "same key" in message or "unique key" in message:
                react_key_warnings.append(message)
        if response.get("id") == seq:
            if "error" in response:
                raise RuntimeError(response["error"])
            return response.get("result", {})


def js(source):
    value = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
    if value.get("exceptionDetails"):
        raise RuntimeError(value["exceptionDetails"])
    return value.get("result", {}).get("value")


def until(source, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = js(source)
        if value:
            return value
        time.sleep(.25)
    raise AssertionError(f"timeout: {source}; url={js('location.href')}; body={js('document.body.innerText.slice(0,900)')}; alerts={js('[...document.querySelectorAll("[role=alert]")].map(x=>x.textContent)')}")


def click(label, selector="button"):
    return js("(() => {const e=[...document.querySelectorAll(%s)].find(x=>x.textContent.trim().includes(%s));if(!e)return false;e.click();return true})()" % (json.dumps(selector), json.dumps(label)))


def fill(selector, value):
    return js("(() => {const e=document.querySelector(%s);if(!e)return false;const setter=Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set;setter.call(e,%s);e.dispatchEvent(new Event('input',{bubbles:true}));return true})()" % (json.dumps(selector), json.dumps(str(value))))


def api_action(session, project_id, csrf, route, body):
    response = session.post(f"{API}/api/brain/projects/{project_id}/{route}", json=body, headers={"X-CSRF-Token": csrf}, timeout=40)
    assert response.ok, (route, response.status_code, response.text[:500])
    return response.json()


def choose_model():
    selector = "[...document.querySelectorAll('[aria-label=\"Расчёт и результат\"] label')].find(e=>e.textContent.includes('Модель из активного расчётного каталога'))?.querySelector('select')"
    until(f"({selector})?.options.length > 1")
    assert js(f"(() => {{const e={selector};e.value=e.options[1].value;e.dispatchEvent(new Event('change',{{bubbles:true}}));return Boolean(e.value)}})()")


try:
    active = browser_profile / "DevToolsActivePort"
    for _ in range(80):
        if active.exists():
            break
        time.sleep(.2)
    assert active.exists()
    port = active.read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=3).json()
    ws = websocket.create_connection(next(item["webSocketDebuggerUrl"] for item in pages if item["type"] == "page"), timeout=5)
    call("Runtime.enable")
    call("Emulation.setDeviceMetricsOverride", {"width": 390 if MOBILE else 1366, "height": 844 if MOBILE else 768,
                                                  "deviceScaleFactor": 1, "mobile": MOBILE})
    session = requests.Session()
    registered = session.post(f"{API}/api/auth/register", json={"email": f"stage31-{uuid.uuid4().hex[:12]}@example.com",
        "password": "Stage31-local-only-2026", "name": "Проверка Brain"}, timeout=10)
    assert registered.status_code == 201, registered.text
    csrf = registered.json()["csrf_token"]
    project_response = session.post(f"{API}/api/projects", json={"name": "Этап 3.1 · одноразовый склад"},
                                    headers={"X-CSRF-Token": csrf}, timeout=10)
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()
    project_id = project["id"]
    for cookie in session.cookies:
        call("Network.setCookie", {"name": cookie.name, "value": cookie.value, "url": WEB})
    call("Page.navigate", {"url": f"{WEB}/#model"})
    until("Boolean(document.querySelector('[aria-label=\"Моделирование процесса\"]'))")
    until("document.body.innerText.includes('Профиль расчёта')")
    assert fill('[aria-label="Диалог Brain"] textarea', 'На складе перевозим 220 паллет в сутки на 120 м')
    assert click('Отправить', '[aria-label="Диалог Brain"] button')
    until("document.body.innerText.includes('Локально распознаны только явно названные значения')")
    stored = session.get(f"{API}/api/brain/projects/{project_id}", timeout=10).json()
    assert stored["versions"][-1]["utterance"] == 'На складе перевозим 220 паллет в сутки на 120 м'
    version = stored["profile"]["profile_version"]
    for field, value in [
        ("object_type", "retail"), ("process_type", "transport"), ("operations_per_day", "220"),
        ("shifts_count", "2"), ("shift_hours", "11"), ("operating_days", "365"),
        ("avg_distance_m", "120"), ("units_per_trip", "1"), ("exchange_seconds", "90"),
        ("zone_label", "Основная зона"), ("staff_headcount", "8"),
    ]:
        saved = api_action(session, project_id, csrf, "edit", {"expected_version": version, "field": field, "value": value, "confirmed": True})
        version = saved["profile"]["profile_version"]
    call("Page.reload")
    until("document.body.innerText.includes('версия профиля: %s')" % version)
    assert js("document.body.innerText.includes('220 паллет/сутки')")
    assert click('Подтвердить профиль', '[aria-label="Профиль расчёта"] button')
    until("document.body.innerText.includes('версия профиля: %s')" % (version + 1))
    choose_model()
    assert click('Рассчитать и сохранить', '[aria-label="Расчёт и результат"] button')
    until("Boolean(document.querySelector('.capacity-results-v2'))", 45)
    until("Boolean(document.querySelector('form.economics-inputs-v2'))")
    first_run = session.get(f"{API}/api/brain/projects/{project_id}", timeout=10).json()["profile"]["runs"][0]
    assert first_run["run_kind"] == "CAPACITY_ANALYSIS"
    assert click('Сохранить частичный результат', 'form.economics-inputs-v2 button')
    until("Boolean(document.querySelector('[aria-label=\"Частичный результат экономики\"]'))", 45)
    assert js("document.body.innerText.includes('Не рассчитано')")
    report = session.get(f"{API}/api/projects/{project_id}/analysis-runs/{first_run['run_id']}/exports/report-preview.pdf", timeout=30)
    assert report.ok and report.content.startswith(b"%PDF")
    first_pdf = report.content
    print("PASS: own 220 pallets/day and 120 m, partial economics and PDF", flush=True)
    if MOBILE:
        assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    image = ROOT / ".tmp" / ("stage31-mobile.png" if MOBILE else "stage31-desktop.png")
    image.write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
    print("SCREENSHOT:", image, flush=True)
    current = session.get(f"{API}/api/brain/projects/{project_id}", timeout=10).json()["profile"]
    changed = api_action(session, project_id, csrf, "edit", {"expected_version": current["profile_version"],
        "field": "operations_per_day", "value": "260", "confirmed": True})
    assert changed["profile"]["parent_version"] == current["profile_version"]
    call("Page.reload")
    until("document.body.innerText.includes('версия профиля: %s')" % changed["profile"]["profile_version"])
    assert js("document.body.textContent.includes('220 → 260')")
    assert session.get(f"{API}/api/projects/{project_id}/analysis-runs/{first_run['run_id']}/exports/report-preview.pdf", timeout=30).content == first_pdf
    print("PASS: what-if child version and old PDF unchanged", flush=True)
    version = changed["profile"]["profile_version"]
    for field, value in [("operations_per_day", "2000"), ("staff_headcount", "25"),
                         ("monthly_gross_salary", "120000"), ("manual_units_per_shift", "100")]:
        saved = api_action(session, project_id, csrf, "edit", {"expected_version": version, "field": field,
            "value": value, "confirmed": True, "provenance": "expert_assumption"})
        version = saved["profile"]["profile_version"]
    call("Page.reload")
    until("document.body.innerText.includes('версия профиля: %s')" % version)
    assert click('Подтвердить профиль', '[aria-label="Профиль расчёта"] button')
    until("document.body.innerText.includes('версия профиля: %s')" % (version + 1))
    choose_model()
    assert click('Рассчитать и сохранить', '[aria-label="Расчёт и результат"] button')
    until("Boolean(document.querySelector('.capacity-results-v2'))", 45)
    until("Boolean(document.querySelector('form.economics-inputs-v2'))")
    assert click('Предложить все числа', 'form.economics-inputs-v2 button')
    assert click('Подтвердить допущения', 'form.economics-inputs-v2 button')
    assert js("(() => {const boxes=[...document.querySelectorAll('form.economics-inputs-v2 [id^=economics-condition-]')];boxes.forEach(x=>{if(!x.checked)x.click()});return boxes.length})()") == 5
    assert click('Полный расчёт', 'form.economics-inputs-v2 button')
    until("Boolean(document.querySelector('[aria-label=\"Коммерческие сценарии\"]'))", 55)
    runs = session.get(f"{API}/api/brain/projects/{project_id}", timeout=10).json()["profile"]["runs"]
    assert [item["run_kind"] for item in runs] == ["CAPACITY_ANALYSIS", "FULL_ANALYSIS"]
    full_pdf = session.get(f"{API}/api/projects/{project_id}/analysis-runs/{runs[-1]['run_id']}/exports/report-preview.pdf", timeout=30)
    assert full_pdf.ok and full_pdf.content.startswith(b"%PDF")
    js("document.body.innerText.length")
    assert not react_key_warnings, react_key_warnings
    print("PASS: typical warehouse, five confirmations, full economics and PDF", flush=True)
finally:
    if ws:
        ws.close()
    chrome.terminate()
    chrome.wait(timeout=10)
