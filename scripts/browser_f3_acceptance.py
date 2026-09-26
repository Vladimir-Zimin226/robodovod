"""F3 manual UI journey and historical integrity; local stage11_* DB only."""

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
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".tmp/f3/acceptance"
OUT.mkdir(parents=True, exist_ok=True)
url = os.environ["F3_DATABASE_URL"].replace("postgresql+psycopg:", "postgresql:")
parsed = urlparse(url)
assert parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path.startswith(
    "/stage11_"
)
API, WEB = "http://127.0.0.1:8000", "http://127.0.0.1:5173"


def rows(table):
    assert table in {
        "analysis_runs",
        "simulation_artifacts",
        "catalog_versions",
        "admin_catalog_documents",
    }
    with psycopg.connect(url) as db:
        return {
            str(row[0]): row[1]
            for row in db.execute(
                f"SELECT {'catalog_version_id' if table == 'admin_catalog_documents' else 'id'}, row_to_json(r) FROM {table} r"
            )
        }


history, artifacts, versions, documents = (
    rows(table)
    for table in (
        "analysis_runs",
        "simulation_artifacts",
        "catalog_versions",
        "admin_catalog_documents",
    )
)
owner = requests.Session()
with psycopg.connect(url) as db:
    email = db.execute(
        "SELECT email_normalized FROM users WHERE email_normalized LIKE 'stage31-%' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()[0]
auth = owner.post(
    API + "/api/auth/login",
    json={"email": email, "password": "Stage31-local-only-2026"},
    timeout=10,
)
assert auth.ok
old_project = next(
    project
    for project in owner.get(API + "/api/projects", timeout=10).json()["items"]
    if "одноразовый склад" in project["name"]
)
old_runs = owner.get(
    f"{API}/api/projects/{old_project['id']}/analysis-runs", timeout=10
).json()["items"]
selected_old = []
for demand in ("220", "2000"):
    for row in old_runs:
        if row["run_kind"] != "FULL_ANALYSIS":
            continue
        result = owner.get(
            f"{API}/api/projects/{old_project['id']}/analysis-runs/{row['id']}",
            timeout=10,
        ).json()
        if (result.get("scenario_spec_snapshot") or {}).get("tasks", [{}])[0].get(
            "demand", {}
        ).get("value") == demand:
            selected_old.append(result)
            break
assert len(selected_old) == 2
old_exports = {}
for run in selected_old:
    for filename in ("report.pdf", "evidence.zip"):
        route = f"/api/projects/{old_project['id']}/analysis-runs/{run['id']}/exports/{filename}"
        response = owner.get(API + route, timeout=45)
        assert response.ok, (route, response.status_code, response.text[:200])
        old_exports[route] = hashlib.sha256(response.content).hexdigest()
        if filename == "evidence.zip":
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                for artifact in manifest["artifacts"]:
                    assert (
                        artifact["sha256"]
                        == "sha256:"
                        + hashlib.sha256(archive.read(artifact["filename"])).hexdigest()
                    )

# Reopen a real saved F2 workbook through its owner API, using the existing
# disposable file root. File bytes are read only throughout this journey.
with psycopg.connect(url) as db:
    saved_file = next(
        row
        for row in db.execute(
            "SELECT f.project_id,f.id,f.storage_key,u.email_normalized FROM project_files f JOIN projects p ON p.id=f.project_id JOIN users u ON u.id=p.owner_id WHERE u.email_normalized LIKE 'f2-%'"
        )
        if (ROOT / ".tmp/f2/backend-data/uploads" / row[2]).is_file()
    )
file_owner = requests.Session()
assert file_owner.post(
    API + "/api/auth/login",
    json={"email": saved_file[3], "password": "F2-local-only-2026"},
    timeout=10,
).ok
file_route = f"/api/projects/{saved_file[0]}/files/{saved_file[1]}"
old_xlsx = file_owner.get(API + file_route, timeout=10)
assert old_xlsx.ok, old_xlsx.text
old_xlsx_sha = hashlib.sha256(old_xlsx.content).hexdigest()

session = requests.Session()
registered = session.post(
    API + "/api/auth/register",
    json={
        "email": f"f3-{uuid.uuid4().hex}@example.com",
        "password": "F3-local-only-2026",
        "name": "F3 local admin",
    },
    timeout=10,
)
assert registered.status_code == 201
with psycopg.connect(url) as db:
    db.execute(
        "UPDATE users SET role='ADMIN' WHERE id=%s AND email_normalized LIKE 'f3-%%'",
        (registered.json()["user"]["id"],),
    )
headers = {"X-CSRF-Token": registered.json()["csrf_token"]}
profile_path = Path(tempfile.mkdtemp(prefix="f3-chrome-", dir=ROOT / ".tmp"))
chrome = subprocess.Popen(
    [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        "--remote-debugging-port=0",
        f"--user-data-dir={profile_path}",
        "about:blank",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
ws, seq = None, 0
browser_errors = []


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


def record(code):
    response = session.get(f"{API}/api/admin/catalog/versions/{code}", timeout=20)
    assert response.ok, response.text
    return response.json()


def validate_publish():
    click("Проверить версию")
    until('document.querySelector("[role=status]")?.textContent.includes("проверена")')
    checkbox("Я проверил diff")
    click("Опубликовать версию")
    until(
        'document.querySelector("[role=status]")?.textContent.includes("опубликована")'
    )


def activate():
    checkbox("Я проверил diff")
    click("Активировать выбранную")
    until(
        'document.querySelector("[role=status]")?.textContent.includes("переключена")'
    )


try:
    for _ in range(80):
        if (profile_path / "DevToolsActivePort").exists():
            break
        time.sleep(0.2)
    port = (profile_path / "DevToolsActivePort").read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
    ws = websocket.create_connection(
        next(page["webSocketDebuggerUrl"] for page in pages if page["type"] == "page"),
        timeout=20,
    )
    call("Runtime.enable")
    call("Page.enable")
    call(
        "Emulation.setDeviceMetricsOverride",
        {"width": 1366, "height": 768, "deviceScaleFactor": 1, "mobile": False},
    )
    downloads = OUT / "downloads"
    downloads.mkdir(exist_ok=True)
    call(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(downloads)},
    )
    for cookie in session.cookies:
        call(
            "Network.setCookie",
            {"name": cookie.name, "value": cookie.value, "url": WEB},
        )
    call("Page.navigate", {"url": WEB + "/#account"})
    until('document.body.innerText.includes("F3 local admin")')
    click("Каталог и источники")
    until(
        'document.querySelector(`[aria-label="Администрирование каталога"]`) !== null'
    )
    until(
        '[...document.querySelectorAll("select option")].some(e=>e.value==="organizer-catalog-v4")'
    )
    field("Версия для просмотра или возврата", "organizer-catalog-v4", select=True)
    until('document.body.innerText.includes("исходная")')
    code = "f3-browser-" + uuid.uuid4().hex[:12]
    field("Код новой версии", code)
    click("Создать черновик")
    until(
        'document.querySelector("[role=status]")?.textContent.includes("Черновик создан")'
    )
    click("Источники")
    click("Добавить источник")
    field("URL", "https://example.com/f3-local-spec")
    field("Документ / ссылка на хранилище", "F3 local reviewed document")
    field("Комментарий источника", "Synthetic acceptance data")
    click("Решения и ТТХ")
    click("Добавить решение")
    field("Название", "F3 manual informational robot")
    field("Производитель", "F3 test manufacturer")
    field("Семейство", "AGV_AMR")
    field("Тип", "F3_TEST_TYPE")
    field("Страна", "RU")
    field("Доступность", "PROTOTYPE")
    field("Назначение", "Local informational transport solution")
    field("Инфраструктура", "WMS required")
    field("Срок службы, лет · пусто = неизвестно", "8")
    click("Добавить характеристику")
    # Unknown payload stays null; not silently converted to zero or calculation readiness.
    click("Предложения")
    click("Добавить предложение")
    field("Цена · пусто = неизвестно", "1000000")
    field("Валюта, ISO", "RUB")
    field("НДС · INCLUDED / EXCLUDED / UNKNOWN", "INCLUDED")
    field("Отрасль", "Склад")
    field("Применимость / сценарий", "Transport")
    field("Включённые услуги · через ;", "Installation; support")
    click("Добавить предложение")
    field("Цена · пусто = неизвестно", "2000000")
    field("Валюта, ISO", "RUB")
    field("НДС · INCLUDED / EXCLUDED / UNKNOWN", "EXCLUDED")
    click("Нормы")
    click("Добавить exchange_seconds")
    field("Значение нормы", "40")
    field("Верхняя граница", "60")
    field("Основание нормы", "F3 scenario proposal; confirm in new profile")
    click("Справочники")
    click("Добавить запись справочника")
    field("Код справочника", "F3_TEST_TYPE")
    field("Название", "Local transport type")
    click("Сохранить и показать diff")
    until(
        'document.querySelector("[role=status]")?.textContent.includes("Изменения сохранены")'
    )
    saved = record(code)
    assert len(saved["diff"]) == 6, len(saved["diff"])
    new_model = next(
        model
        for model in saved["document"]["models"]
        if model["name"] == "F3 manual informational robot"
    )
    assert new_model["specs"][0]["value"] is None
    assert not next(
        model for model in saved["model_readiness"] if model["key"] == new_model["key"]
    )["ready"]
    click("Решения и ТТХ")
    field("Решение", new_model["key"], select=True)
    screenshot("manual-draft-desktop.png")
    validate_publish()
    checkbox("Переключить discovery и capacity вместе")
    activate()
    discovered = session.get(
        API + "/api/catalog/models?q=F3%20manual%20informational", timeout=20
    ).json()
    assert discovered["catalog"]["code"] == code and len(discovered["items"]) == 2
    assert sorted(item["purchase"]["amount"] for item in discovered["items"]) == [
        1000000,
        2000000,
    ]
    assert all(not item["calculation_ready"] for item in discovered["items"])
    imported_code = code + "-import"
    field("Код новой версии", imported_code)
    click("Скачать JSON для обновления")
    for _ in range(50):
        files = [
            item
            for item in downloads.glob("*.json")
            if json.loads(item.read_text(encoding="utf-8")).get("code") == imported_code
        ]
        if files:
            break
        time.sleep(0.2)
    file = files[-1]
    envelope = json.loads(file.read_text(encoding="utf-8"))
    assert envelope["code"] == imported_code

    def upload():
        root = call("DOM.getDocument")["root"]["nodeId"]
        node = call(
            "DOM.querySelector", {"nodeId": root, "selector": "input[type=file]"}
        )["nodeId"]
        call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(file)]})
        until(
            f'document.querySelector("h2")?.textContent.includes({json.dumps(imported_code)})'
        )
        until(
            'document.querySelector("[role=status]")?.textContent.includes("Импорт проверен")'
        )

    upload()
    upload()
    assert record(imported_code)["revision"] == 1
    click("Решения и ТТХ")
    field("Решение", new_model["key"], select=True)
    field("Название", "F3 manual imported revision")
    field("Значение · пусто = неизвестно · NUMBER", "1000")
    field("Подтверждение", "MANUALLY_APPROVED", select=True)
    field("Источник", saved["document"]["sources"][-1]["key"], select=True)
    field("Комментарий проверки", "F3 reviewed payload; rollout still required")
    click("Сохранить и показать diff")
    until(
        'document.querySelector("[role=status]")?.textContent.includes("Изменения сохранены")'
    )
    validate_publish()
    activate()
    # Return the active pointers through the same UI, including explicit expected versions.
    field("Версия для просмотра или возврата", code, select=True)
    until(
        f'document.querySelector("h2")?.textContent.includes({json.dumps(code + " · PUBLISHED")})'
    )
    activate()
    listing = session.get(API + "/api/admin/catalog", timeout=15).json()
    assert all(item["catalog_code"] == code for item in listing["active"])
    click("Показать аудит")
    until('document.body.innerText.includes("ADMIN_CATALOG_ACTIVATED")')
    screenshot("published-rollback-desktop.png")
    call(
        "Emulation.setDeviceMetricsOverride",
        {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
    )
    click("Решения и ТТХ")
    field("Решение", new_model["key"], select=True)
    assert js("document.documentElement.scrollWidth <= innerWidth + 1"), (
        "mobile overflow"
    )
    screenshot("published-mobile.png")
    # Apply a norm through the user UI, then separately confirm and calculate.
    # The older profile version stays unchanged; the C11 input carries 40 s.
    project = session.post(
        API + "/api/projects",
        headers=headers,
        json={"name": "F3 norm warehouse"},
        timeout=10,
    ).json()
    profile = session.get(
        f"{API}/api/brain/projects/{project['id']}", timeout=10
    ).json()["profile"]
    for name, value in [
        ("object_type", "retail"),
        ("process_type", "transport"),
        ("operations_per_day", "220"),
        ("shifts_count", "2"),
        ("shift_hours", "11"),
        ("operating_days", "250"),
        ("avg_distance_m", "120"),
        ("units_per_trip", "1"),
    ]:
        response = session.post(
            f"{API}/api/brain/projects/{project['id']}/edit",
            headers=headers,
            json={
                "expected_version": profile["profile_version"],
                "field": name,
                "value": value,
                "provenance": "user",
                "confirmed": True,
            },
            timeout=10,
        )
        assert response.ok, response.text
        profile = response.json()["profile"]
    call(
        "Emulation.setDeviceMetricsOverride",
        {"width": 1366, "height": 768, "deviceScaleFactor": 1, "mobile": False},
    )
    call("Page.navigate", {"url": WEB + "/#model"})
    until('location.hash === "#model"')
    call("Page.reload")
    until('document.body.innerText.includes("Предложить Погрузка и выгрузка")')
    click("Предложить Погрузка и выгрузка")
    until('document.body.innerText.includes("40 сек")')
    proposed = session.get(
        f"{API}/api/brain/projects/{project['id']}", timeout=10
    ).json()
    assert not proposed["profile"]["fields"]["exchange_seconds"]["confirmed_by_user"]
    assert proposed["versions"][-2] == profile
    click("Подтвердить профиль")
    until(
        '[...document.querySelectorAll("button")].some(e=>e.textContent==="Рассчитать и сохранить")'
    )
    assert js(
        '(()=>{const label=[...document.querySelectorAll("label")].find(e=>e.textContent.startsWith("Модель из активного расчётного каталога"));const e=label.querySelector("select");e.value=e.options[1].value;e.dispatchEvent(new Event("change",{bubbles:true}));return Boolean(e.value)})()'
    )
    until(
        '[...document.querySelectorAll("button")].some(e=>e.textContent==="Рассчитать и сохранить"&&!e.disabled)'
    )
    click("Рассчитать и сохранить")
    until('document.body.innerText.includes("Технический run:")')
    norm_runs = session.get(
        f"{API}/api/projects/{project['id']}/analysis-runs", timeout=10
    ).json()["items"]
    norm_run = session.get(
        f"{API}/api/projects/{project['id']}/analysis-runs/{norm_runs[0]['id']}",
        timeout=10,
    ).json()
    assert (
        norm_run["input_snapshot"]["process"]["exchange"]["total_time"][
            "normalized_value"
        ]
        == "40"
    )
    assert norm_run["versions"]["catalog"] == code
    screenshot("confirmed-norm-calculation.png")
    # A new calculation binds to the activated catalog; the immutable request is
    # copied from each historical warehouse run rather than changing that run.
    new_runs = []
    for old in selected_old:
        capacity_id = old["input_snapshot"]["capacity_run_id"]
        prior = owner.get(
            f"{API}/api/projects/{old_project['id']}/analysis-runs/{capacity_id}",
            timeout=15,
        ).json()
        body = prior["input_snapshot"]
        response = owner.post(
            API + "/api/v2/capacity-analyses",
            headers={"X-CSRF-Token": auth.json()["csrf_token"]},
            json=body,
            timeout=40,
        )
        assert response.status_code == 201, response.text
        rid = response.json()["run_id"]
        new = owner.get(
            f"{API}/api/projects/{old_project['id']}/analysis-runs/{rid}", timeout=15
        ).json()
        assert new["versions"]["catalog"] == code
        assert (
            new["result_snapshot"]["capacity"]["value"]
            == prior["result_snapshot"]["capacity"]["value"]
        )
        economic = owner.post(
            f"{API}/api/v2/projects/{old_project['id']}/economics-runs",
            headers={"X-CSRF-Token": auth.json()["csrf_token"]},
            timeout=45,
            json={
                "scenario_id": old["scenario_id"],
                "capacity_run_id": rid,
                "source_run_id": old["id"],
                "input": {
                    "schema_version": "economics-explicit-inputs-v4",
                    "input_revision": body["input_revision"],
                    "start_seconds_from_midnight": "32400",
                    "timezone": "Asia/Sakhalin",
                },
            },
        )
        assert economic.status_code == 201, economic.text
        assert economic.json()["versions"]["catalog"] == code
        new_runs.append(
            {
                "run_id": rid,
                "catalog_version": code,
                "demand": body["process"]["demand"]["normalized_value"],
            }
        )
    # Every historical row and every published version/document remains byte-equivalent
    # in canonical JSON. Saved artifacts must not be rewritten, including checksums.
    for table, before in (
        ("analysis_runs", history),
        ("simulation_artifacts", artifacts),
        ("catalog_versions", versions),
        ("admin_catalog_documents", documents),
    ):
        after = rows(table)
        assert all(after[key] == value for key, value in before.items()), table
    for route, expected in old_exports.items():
        response = owner.get(API + route, timeout=45)
        assert (
            response.ok and hashlib.sha256(response.content).hexdigest() == expected
        ), route
    reopened_xlsx = file_owner.get(API + file_route, timeout=10)
    assert (
        reopened_xlsx.ok
        and hashlib.sha256(reopened_xlsx.content).hexdigest() == old_xlsx_sha
    )
    assert not browser_errors, browser_errors
    report = {
        "manual_catalog_code": code,
        "imported_catalog_code": imported_code,
        "diff_count": len(saved["diff"]),
        "new_runs": new_runs,
        "historical_runs_unchanged": len(history),
        "historical_artifacts_unchanged": len(artifacts),
        "catalog_versions_unchanged": len(versions),
        "published_versions_unchanged": sum(item["status"] == "PUBLISHED" for item in versions.values()),
        "catalog_documents_unchanged": len(documents),
        "old_exports_sha256": old_exports,
        "duplicate_offers": [1000000, 2000000],
        "browser_errors": browser_errors,
        "saved_xlsx_unchanged": {"route": file_route, "sha256": old_xlsx_sha},
        "confirmed_norm_run": {
            "run_id": norm_run["id"],
            "catalog_version": code,
            "exchange_seconds": "40",
        },
        "checks": [
            "ADMIN manual model/offers/source/default/dictionary",
            "preview/validate/publish/atomic activation",
            "JSON download/import/idempotent repeat/edit/publish",
            "UI rollback",
            "desktop/mobile",
            "new version calculation",
            "immutable history",
        ],
    }
    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
finally:
    if ws:
        ws.close()
    chrome.terminate()
    try:
        chrome.wait(timeout=10)
    except subprocess.TimeoutExpired:
        chrome.kill()
