"""Read-only F4 API/UI acceptance on retained disposable localhost history."""

import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".tmp/f4/acceptance"
OUT.mkdir(parents=True, exist_ok=True)
url = os.environ["F4_DATABASE_URL"].replace("postgresql+psycopg:", "postgresql:")
parsed = urlparse(url)
assert (
    parsed.hostname == "127.0.0.1"
    and parsed.port == 5541
    and parsed.path == "/stage11_f1_browser"
)
API, WEB = "http://127.0.0.1:8000", "http://127.0.0.1:5173"


def history():
    with psycopg.connect(url) as db:
        return {
            table: {
                str(row[0]): row[1]
                for row in db.execute(f"SELECT id,row_to_json(r) FROM {table} r")
            }
            for table in ("analysis_runs", "simulation_artifacts", "catalog_versions")
        }


before = history()


def catalog(**params):
    response = requests.get(API + "/api/catalog/models", params=params, timeout=30)
    assert response.ok, response.text
    return response.json()


all_items = catalog()
counts = {
    kind: catalog(object_kind=kind)["total"]
    for kind in ("warehouse", "airport", "clinic")
}
assert len(set(counts.values())) == 3 and all(value > 0 for value in counts.values()), (
    counts
)
transport = catalog(
    object_kind="warehouse",
    process_code="warehouse_receiving_shipping",
    include_unknown=True,
)
cleaning = catalog(
    object_kind="warehouse", process_code="warehouse_cleaning", include_unknown=True
)
assert {p["id"] for p in transport["items"]} != {p["id"] for p in cleaning["items"]}
sanitized = catalog(
    object_kind="warehouse",
    process_code="warehouse_cleaning",
    include_unknown=True,
    sanitization_required=True,
)
assert any(
    any(
        c["check_id"] == "sanitization" and c["status"] == "UNKNOWN"
        for c in p["selection"]["checks"]
    )
    for p in sanitized["items"]
)
heavy = catalog(
    object_kind="warehouse",
    process_code="warehouse_receiving_shipping",
    include_unknown=True,
    max_payload_kg="100000",
    min_aisle_width_m="0.01",
)
assert any(p["selection"]["status"] == "EXCLUDED" for p in heavy["items"])
assert any(p["selection"]["status"] == "REQUIRES_CHECK" for p in heavy["items"])
assert all(
    not p["selection"]["calculation_compatible"]
    for p in heavy["items"]
    if p["selection"]["status"] == "EXCLUDED"
)
assert not requests.get(
    API + "/api/catalog/models",
    params={"object_kind": "clinic", "process_code": "warehouse_cleaning"},
).ok
assert not requests.get(
    API + "/api/catalog/models", params={"price_min": 100, "price_max": 1}
).ok
assert not catalog(payload_min=100000)["items"]
assert catalog(payload_min=100000, include_unknown=True)["items"]
report = {
    "catalog": all_items["catalog"]["code"],
    "total": all_items["total"],
    "objects": counts,
    "transport": transport["total"],
    "cleaning": cleaning["total"],
    "history": {t: len(v) for t, v in before.items()},
}


def call(method, params=None):
    global seq
    seq += 1
    ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get("method") == "Runtime.exceptionThrown":
            browser_errors.append(result["params"])
        if (
            result.get("method") == "Runtime.consoleAPICalled"
            and result["params"]["type"] == "error"
        ):
            browser_errors.append(result["params"])
        if result.get("id") == seq:
            assert "error" not in result, result
            return result.get("result", {})


def js(source):
    result = call(
        "Runtime.evaluate",
        {"expression": source, "returnByValue": True, "awaitPromise": True},
    )
    assert "exceptionDetails" not in result, result
    return result.get("result", {}).get("value")


def until(source, seconds=40):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = js(source)
        if result:
            return result
        time.sleep(0.2)
    raise AssertionError(f"{source}; body={js('document.body.innerText')}")


def click(label, selector="button"):
    until(
        f"Boolean([...document.querySelectorAll({json.dumps(selector)})].find(e=>e.textContent.trim().includes({json.dumps(label)})&&!e.disabled))"
    )
    assert js(
        f"(()=>{{const e=[...document.querySelectorAll({json.dumps(selector)})].find(e=>e.textContent.trim().includes({json.dumps(label)}));if(!e||e.disabled)return false;e.click();return true}})()"
    ), label


def field(label, value, *, select=False):
    assert js(
        "(()=>{{const label=[...document.querySelectorAll('label')].find(e=>e.textContent.trim().startsWith({}));const e=label?.querySelector({});if(!e||e.disabled)return false;{};e.dispatchEvent(new Event({},{{bubbles:true}}));e.dispatchEvent(new FocusEvent('blur',{{bubbles:true}}));e.dispatchEvent(new FocusEvent('focusout',{{bubbles:true}}));return true}})()".format(
            json.dumps(label),
            json.dumps("select" if select else "input"),
            f"e.value={json.dumps(str(value))}"
            if select
            else f"Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,{json.dumps(str(value))})",
            json.dumps("change" if select else "input"),
        )
    ), label


def checkbox(text):
    assert js(
        f"(()=>{{const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes({json.dumps(text)}));const e=label?.querySelector('input[type=checkbox]');if(!e)return false;e.click();return true}})()"
    )


def screenshot(name):
    (OUT / name).write_bytes(
        base64.b64decode(
            call("Page.captureScreenshot", {"captureBeyondViewport": False})["data"]
        )
    )


profile_path = Path(tempfile.mkdtemp(prefix="f4-chrome-", dir=ROOT / ".tmp"))
chrome = subprocess.Popen(
    [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--remote-allow-origins=*",
        "--remote-debugging-port=0",
        f"--user-data-dir={profile_path}",
        "about:blank",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
ws, seq, browser_errors = None, 0, []
try:
    deadline = time.monotonic() + 30
    while not (profile_path / "DevToolsActivePort").exists():
        assert time.monotonic() < deadline
        time.sleep(0.2)
    port = (profile_path / "DevToolsActivePort").read_text().splitlines()[0]
    target = next(
        page
        for page in requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        if page["type"] == "page"
    )
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
    call("Runtime.enable")
    call("Page.enable")
    call("Page.navigate", {"url": WEB + "/#catalog"})
    try:
        until("Boolean(document.querySelector('#catalog-title'))")
    except AssertionError as exc:
        raise AssertionError(
            (str(exc), js("location.href"), js("document.readyState"), browser_errors)
        ) from exc
    until("document.querySelectorAll('.catalog-card').length>0")
    for width, height in ((1366, 768), (390, 844)):
        if width == 390:
            call("Page.navigate", {"url": WEB + "/?f4=mobile#catalog"})
            until("document.querySelectorAll('.catalog-card').length>0")
        call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": width == 390,
            },
        )
        for kind in ("warehouse", "airport", "clinic"):
            field("Объект", kind, select=True)
            until(
                f"document.querySelector('.catalog-heading').innerText.includes('{counts[kind]} позиций')"
            )
            assert js("document.documentElement.scrollWidth <= window.innerWidth+1")
            screenshot(f"{kind}-{width}.png")
        click("Сбросить фильтры")
        until(
            f"document.querySelector('.catalog-heading').innerText.includes('{all_items['total']} позиций')"
        )
        field("Объект", "warehouse", select=True)
        field("Процесс", "warehouse_receiving_shipping", select=True)
        click("Дополнительные фильтры", "summary")
        checkbox("Включить неизвестные")
        field("Масса груза объекта", "100000")
        until(
            "[...document.querySelectorAll('.catalog-card')].some(e=>e.innerText.includes('EXCLUDED'))"
        )
        time.sleep(1)
        cards = js(
            "[...document.querySelectorAll('.catalog-card')].map(e=>e.innerText)"
        )
        assert any("EXCLUDED" in c for c in cards), cards
        assert js(
            "(()=>{const x=[...document.querySelectorAll('.catalog-card')].find(e=>e.innerText.includes('EXCLUDED'));x?.querySelector('.catalog-card-footer button')?.click();return Boolean(x)})()"
        )
        until(
            "[...document.querySelectorAll('.catalog-card-footer button')].filter(e=>e.innerText.includes('В сравнении')).length===1"
        )
        assert js(
            "(()=>{const y=[...document.querySelectorAll('.catalog-card')].find(e=>!e.querySelector('.catalog-card-footer button')?.innerText.includes('В сравнении'));y?.querySelector('.catalog-card-footer button')?.click();return Boolean(y)})()"
        )
        click("Сравнить позиции")
        until("document.querySelector('[role=dialog]')?.innerText.includes('EXCLUDED')")
        assert js(
            "document.querySelector('[role=dialog]').innerText.includes('источник')"
        )
        screenshot(f"excluded-comparison-{width}.png")
        js("document.querySelector('[aria-label=\"Закрыть сравнение\"]').click()")
        click("Сбросить фильтры")
    assert not browser_errors, browser_errors
    assert history() == before
    report["browser_errors"] = browser_errors
    report["history_unchanged"] = True
    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
finally:
    if ws:
        ws.close()
    chrome.terminate()
