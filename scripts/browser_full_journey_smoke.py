"""Full Chrome route against localhost:5173 with a disposable seeded PostgreSQL.

Requires Chrome, the backend on localhost:8000, Vite on localhost:5173,
the published official catalog with media, and active capacity/economics v2.
Creates test accounts and immutable runs in that disposable database.
"""
import json
import os
import subprocess
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import requests
import websocket
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path(tempfile.mkdtemp(prefix="stage8-chrome-", dir=ROOT / ".tmp"))
DOWNLOADS = Path(tempfile.mkdtemp(prefix="stage8-download-", dir=ROOT / ".tmp"))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome = subprocess.Popen([
    CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
    "--no-default-browser-check", "--remote-allow-origins=*",
    "--remote-debugging-port=0", f"--user-data-dir={PROFILE}",
    "http://127.0.0.1:5173/#account",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
ws = None
counter = 0


def call(method, params=None):
    global counter
    counter += 1
    ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
    while True:
        result = json.loads(ws.recv())
        if result.get("id") == counter:
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("result", {})


def js(source):
    result = call("Runtime.evaluate", {"expression": source, "returnByValue": True, "awaitPromise": True})
    if result.get("exceptionDetails"):
        raise RuntimeError(result["exceptionDetails"])
    return result.get("result", {}).get("value")


def until(source, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = js(source)
        if value:
            return value
        time.sleep(.2)
    raise AssertionError(f"Timed out: {source}; page={js('document.body.innerText.slice(-1200)')}")


def fill(selector, value):
    return js("""(() => { const el=document.querySelector(%s); if (!el) return false;
      const setter=Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,'value').set;
      setter.call(el,%s); el.dispatchEvent(new Event('input',{bubbles:true})); return true; })()""" % (json.dumps(selector), json.dumps(str(value))))


def click_text(selector, label):
    return js("""(() => {const e=[...document.querySelectorAll(%s)].find(x=>x.textContent.trim().includes(%s)); if(!e)return false; e.click();return true})()""" % (json.dumps(selector), json.dumps(label)))


def click_nav(selector, label):
    if mobile:
        js("document.querySelector('.mobile-menu-button').click()")
        until("document.querySelector('.mobile-menu-button')?.getAttribute('aria-expanded') === 'true'")
    return click_text(selector, label)


def check_mobile_width():
    if mobile:
        assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")


def select_first(selector):
    return js("""(() => {const e=document.querySelector(%s); if(!e||e.options.length<2)return false; e.value=e.options[1].value; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value})()""" % json.dumps(selector))


try:
    active = PROFILE / "DevToolsActivePort"
    for _ in range(80):
        if active.exists():
            break
        time.sleep(.2)
    assert active.exists(), "Chrome did not open"
    port = active.read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=3).json()
    ws = websocket.create_connection(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"), timeout=5)
    call("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(DOWNLOADS)})
    mobile = os.getenv('STAGE8_MOBILE') == '1'
    call("Emulation.setDeviceMetricsOverride", {"width": 390 if mobile else 1440, "height": 844 if mobile else 900, "deviceScaleFactor": 1, "mobile": mobile})
    until("Boolean(document.querySelector('.auth-tabs'))")
    assert click_text('.auth-tabs button', 'Регистрация')
    email = f"stage8-{uuid.uuid4().hex[:12]}@example.com"
    assert fill('.auth-screen input[type=email]', email)
    assert fill('.auth-screen input[type=password]', 'Stage8-regression-local-2026')
    assert click_text('.auth-screen button[type=submit]', 'Создать аккаунт')
    until("Boolean(document.querySelector('[aria-label^=\"Аккаунт stage8-\"]'))")
    assert click_text('.account-actions button', 'Мои проекты')
    until("Boolean(document.querySelector('.inline-create input'))")
    assert fill('.inline-create input', 'Этап 8 · проверка')
    assert click_text('.inline-create button', 'Создать')
    until("location.hash === '' && Boolean(document.querySelector('.onboarding-screen'))")
    check_mobile_width()
    print('PASS: account and project', flush=True)

    assert click_nav('.nav-secondary button', 'Библиотека решений')
    until("document.querySelectorAll('.catalog-card').length > 0")
    until("Boolean(document.querySelector('.catalog-card img')?.complete && document.querySelector('.catalog-card img')?.naturalWidth > 0)")
    assert js("document.querySelector('.catalog-notice').textContent.includes('223')")
    js("document.querySelector('.catalog-card-open').click()")
    until("Boolean(document.querySelector('.catalog-detail-dialog'))")
    assert js("Boolean(document.querySelector('.catalog-detail-dialog img')?.naturalWidth > 0)")
    assert click_text('[aria-label="Закрыть подробную карточку"]', '')
    check_mobile_width()
    print('PASS: 223-position catalog, card and detail media', flush=True)

    assert click_nav('.app-nav button', 'Процесс')
    until("Boolean(document.querySelector('#assistant-query'))")
    assert fill('#assistant-query', 'Перевозим 800 паллет в сутки, плечо 180 м, 3 смены')
    js("document.querySelector('.assistant-form button[type=submit]').click()")
    until("document.querySelectorAll('.assistant-card').length >= 2")
    assert js("document.querySelector('.assistant-draft').textContent.includes('800')")
    assert click_text('.assistant-draft button', '')
    until("location.hash === '#calculation'")
    check_mobile_width()
    print('PASS: catalog assistant to calculation', flush=True)

    assert click_nav('.app-nav button', 'Главная')
    until("Boolean(document.querySelector('.onboarding-screen'))")
    js("document.querySelector('.onboarding-screen button').click()")
    until("Boolean(document.querySelector('[aria-label=\"Процессы и роли v2\"]'))")
    assert click_text('[aria-label="Процессы и роли v2"] button', 'Загрузить типовой склад организаторов')
    assert click_text('[aria-label="Процессы и роли v2"] button', 'Открыть')
    assert click_text('[aria-label="Процессы и роли v2"] label', 'Подтверждаю это допущение')
    until("!document.querySelector('[aria-label=\"Процессы и роли v2\"]').innerText.includes('Исправьте обязательные поля')")
    assert click_text('[aria-label="Процессы и роли v2"] button', 'Проверить ввод v2')
    until("Boolean(document.querySelector('[aria-label=\"Предварительный расчёт v2\"]'))")
    until("document.querySelectorAll('[aria-label=\"Предварительный расчёт v2\"] select')[1]?.options.length > 1")
    assert js("(() => {const e=document.querySelectorAll('[aria-label=\"Предварительный расчёт v2\"] select')[1]; if(!e||e.options.length<2)return false; e.value=e.options[1].value; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value})()")
    assert click_text('[aria-label="Предварительный расчёт v2"] label', 'Подтверждаю, что данные типового объекта')
    assert click_text('[aria-label="Предварительный расчёт v2"] button', 'Рассчитать и сохранить v2')
    until("Boolean(document.querySelector('.capacity-results-v2'))", 30)
    check_mobile_width()
    print('PASS: normalized and persisted C11 capacity', flush=True)

    economics = {
        'Ручная производительность': '100', 'Диспетчеры сейчас': '0',
        'Зарплата диспетчера gross': '100000', 'Техники сейчас': '0',
        'Зарплата техника gross': '120000', 'Внедрение и интеграция': '500000',
        'Сервис одного робота': '120000', 'Гарантия': '1',
        'Средняя мощность робота': '1000', 'Общие разовые расходы площадки': '0',
        'Общие ежегодные расходы площадки': '0', 'Горизонт оценки': '5',
        'Ставка дисконтирования': '0.15', 'Тариф RaaS': '180000',
        'Срок договора': '60', 'Начало смены': '28800',
    }
    for label, value in economics.items():
        expression = """(() => {const label=[...document.querySelectorAll('.economics-inputs-v2 label')].find(e=>e.querySelector('strong')?.textContent.startsWith(%s)); const el=label?.querySelector('input'); if(!el)return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,%s); el.dispatchEvent(new Event('input',{bubbles:true})); return true})()""" % (json.dumps(label), json.dumps(value))
        assert js(expression), label
    assert fill('.economics-inputs-v2 input[placeholder="Например, Europe/Moscow"]', 'Europe/Moscow')
    assert js("(() => {const e=[...document.querySelectorAll('.economics-inputs-v2 label')].find(x=>x.textContent.includes('Кто оплачивает инфраструктуру')).querySelector('select'); e.value='VENDOR'; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value})()")
    assert js("(() => {const boxes=[...document.querySelectorAll('.economics-inputs-v2 input[type=checkbox]')]; boxes.forEach(x=>x.click()); return boxes.length})()") >= 5
    assert click_text('.economics-inputs-v2 button[type=submit]', 'Сохранить доступный расчёт')
    until("Boolean(document.querySelector('.commercial-visualization'))", 30)
    assert js("document.querySelector('.commercial-scenario-section').textContent.includes('Сценарии')")
    until("document.querySelector('.evidence-export-v2')?.textContent.includes('Scenarios: AVAILABLE')")
    check_mobile_width()
    print('PASS: immutable economics v2 and six scenarios', flush=True)

    assert click_text('.simulation-run-box button', 'Запустить расчёт симуляции')
    until("Boolean(document.querySelector('.simulation-kpis'))", 90)
    assert js("Boolean(document.querySelector('.robcraft-frame iframe'))")
    until("document.querySelector('.robcraft-frame iframe')?.contentDocument?.readyState === 'complete'", 30)
    assert js("!document.querySelector('.robcraft-frame').textContent.includes('3D-сцена недоступна')")
    assert js("Boolean(document.querySelector('.warehouse-2d-plan') || document.querySelector('.simulation-canvas-wrap svg'))")
    print('PASS: C23 report, 2D scene and RobCraft iframe', flush=True)

    assert click_text('.evidence-export-v2 button', 'Скачать читаемый отчёт PDF')
    until("document.querySelector('.evidence-export-v2')?.textContent.includes('Отчёт скачан')", 30)
    assert click_text('.evidence-export-v2 button', 'Скачать архив ZIP')
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if len(list(DOWNLOADS.glob('*.pdf'))) == 1 and len(list(DOWNLOADS.glob('*.zip'))) == 1 and not list(DOWNLOADS.glob('*.crdownload')):
            break
        time.sleep(.2)
    pdfs, zips = list(DOWNLOADS.glob('*.pdf')), list(DOWNLOADS.glob('*.zip'))
    assert len(pdfs) == len(zips) == 1, [p.name for p in DOWNLOADS.iterdir()]
    assert pdfs[0].name.startswith('Рободовод, отчёт № ')
    assert zips[0].name.startswith('Рободовод, доказательства № ')
    assert 'РОБОДОВОД' in '\n'.join(page.extract_text() for page in PdfReader(pdfs[0]).pages)
    with zipfile.ZipFile(zips[0]) as archive:
        assert archive.testzip() is None
        assert {'НАЧНИТЕ_ЗДЕСЬ.md', 'Отчёт_Рободовод.pdf', 'manifest.json'} <= set(archive.namelist())
        assert archive.read('Отчёт_Рободовод.pdf') == pdfs[0].read_bytes()
    print('PASS: Chrome saved searchable Russian PDF and intact ZIP', flush=True)

    assert click_nav('.nav-secondary button', 'Мои проекты')
    until("Boolean(document.querySelector('.project-card'))")
    assert click_text('.project-card button', 'Расчёты')
    until("document.querySelectorAll('.run-list button').length >= 2")
    js("document.querySelector('.run-list button').click()")
    until("Boolean(document.querySelector('.commercial-screen'))")
    assert js("document.querySelector('.commercial-scenario-section').textContent.includes('Сценарии')")
    assert js("Boolean(document.querySelector('.commercial-visualization'))")
    if js("Boolean(document.querySelector('.simulation-run-box button'))"):
        assert click_text('.simulation-run-box button', 'Запустить расчёт симуляции')
        until("Boolean(document.querySelector('.simulation-kpis'))", 40)
    print('PASS: saved run reopened and C23 replayed', flush=True)

    call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
    mobile = True
    time.sleep(.4)
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    assert js("Boolean(document.querySelector('.commercial-screen'))")
    assert click_nav('.nav-secondary button', 'Библиотека решений')
    until("Boolean(document.querySelector('.catalog-card img')?.naturalWidth > 0)")
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    assert click_nav('.app-nav button', 'Процесс')
    until("Boolean(document.querySelector('#assistant-query'))")
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    print('PASS: mobile 390px result, catalog media and assistant', flush=True)
finally:
    if ws:
        ws.close()
    chrome.terminate()
    try:
        chrome.wait(timeout=5)
    except subprocess.TimeoutExpired:
        chrome.kill()
