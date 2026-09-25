"""Stage 2 readable presentation route against a disposable seeded PostgreSQL.

Requires Chrome, the backend on localhost:8000, Vite on localhost:5173,
the published official catalog with media, and active capacity/economics v2.
Creates test accounts and immutable runs in that disposable database.
"""
import json
import base64
import hashlib
import os
import re
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
SKIP_CATALOG_MEDIA = os.getenv('STAGE1_SKIP_CATALOG_MEDIA') == '1'
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


def screenshot(name):
    if name != 'pdf-preview':
        check_mobile_width()
    target = ROOT / ".tmp" / f"stage2-{name}-{'mobile' if mobile else 'desktop'}.png"
    target.write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    print(f"SCREENSHOT: {target}", flush=True)


def until(source, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = js(source)
        if value:
            return value
        time.sleep(.2)
    raise AssertionError(f"Timed out: {source}; alerts={js('[...document.querySelectorAll(\"[role=alert],.form-error\")].map(e=>e.textContent)')}; page={js('document.body.innerText.slice(-1200)')}")


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


def check_plain_presentation(stage):
    visible = js("document.body.innerText")
    pattern = r"\bC\d{2}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\b(?:MISSING_INPUT|NOT_AVAILABLE|NEEDS_VALIDATION|UNVERIFIED)\b"
    unexplained = [visible[max(0, match.start() - 90):match.end() + 90] for match in re.finditer(pattern, visible, re.I)]
    assert not unexplained, (stage, unexplained)


def interview_field(step, label, value):
    assert js("""(() => {document.querySelectorAll('.assistant-draft nav button')[%s]?.click(); return true})()""" % step)
    until("document.querySelector('.assistant-draft nav button[aria-current=step]')?.textContent.startsWith(%s)" % json.dumps(f'{step + 1}.'))
    changed = js("""(() => {const label=[...document.querySelectorAll('.assistant-draft label')].find(e=>e.firstChild?.textContent?.trim()===%s); const field=label?.querySelector('input,select'); if(!field)return false; const value=%s; if(field.tagName==='SELECT'){field.value=value;field.dispatchEvent(new Event('change',{bubbles:true}));}else{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(field,value);field.dispatchEvent(new Event('input',{bubbles:true}));}return true})()""" % (json.dumps(label), json.dumps(str(value))))
    assert changed, label
    assert js("""(() => {const label=[...document.querySelectorAll('.assistant-draft label')].find(e=>e.firstChild?.textContent?.trim()===%s); const box=label?.parentElement?.querySelector('input[type=checkbox]'); if(!box)return false; if(!box.checked)box.click(); return true})()""" % json.dumps(label)), label


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
    call("Emulation.setDeviceMetricsOverride", {"width": 390 if mobile else 1366, "height": 844 if mobile else 768, "deviceScaleFactor": 1, "mobile": mobile})
    call("Page.navigate", {"url": "http://127.0.0.1:5173/"})
    until("Boolean(document.querySelector('.landing-actions'))")
    check_plain_presentation('landing')
    screenshot('landing')
    assert click_text('.landing-actions button', 'Попробовать демо')
    until("Boolean(document.querySelector('[aria-label=\"Гостевое демо склада\"]'))")
    assert js("document.querySelector('[aria-label=\"Гостевое демо склада\"]').textContent.includes('Закупка: условия закупки не подтверждены')")
    assert js("document.querySelectorAll('[aria-label=\"Экономика демо\"] article').length === 6")
    check_plain_presentation('guest demo')
    screenshot('guest-demo')
    print('PASS: guest warehouse demo and six fixed scenarios', flush=True)
    call("Page.navigate", {"url": "http://127.0.0.1:5173/#account"})
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
    if not SKIP_CATALOG_MEDIA:
        until("Boolean(document.querySelector('.catalog-card img')?.complete && document.querySelector('.catalog-card img')?.naturalWidth > 0)")
    assert js("document.querySelector('.catalog-notice').textContent.includes('223')")
    js("document.querySelector('.catalog-card-open').click()")
    until("Boolean(document.querySelector('.catalog-detail-dialog'))")
    if not SKIP_CATALOG_MEDIA:
        assert js("Boolean(document.querySelector('.catalog-detail-dialog img')?.naturalWidth > 0)")
    assert click_text('[aria-label="Закрыть подробную карточку"]', '')
    check_mobile_width()
    print('PASS: 223-position catalog and detail' + ('' if SKIP_CATALOG_MEDIA else ' media'), flush=True)

    assert click_nav('.app-nav button', 'Процесс')
    until("Boolean(document.querySelector('#assistant-query'))")
    assert fill('#assistant-query', 'Перевозим 220 паллет в сутки, плечо 120 м, 3 смены')
    js("document.querySelector('.assistant-form button[type=submit]').click()")
    until("document.querySelectorAll('.assistant-card').length >= 2")
    assert js("document.querySelector('.assistant-draft').textContent.includes('220')")
    assert js("document.querySelector('.assistant-draft').textContent.includes('Не подтверждено')")
    assert js("(() => {const boxes=[...document.querySelectorAll('.assistant-card-actions input[type=checkbox]')].slice(0,2); boxes.forEach(box=>box.click()); return boxes.length})()") == 2
    assert click_text('.assistant-compare-button', 'Сравнить выбранные')
    until("Boolean(document.querySelector('.assistant-comparison table'))")
    check_mobile_width()
    print('PASS: assistant keeps proposals unconfirmed and compares catalog sources', flush=True)
    check_plain_presentation('assistant')
    screenshot('interview')

    for step, label, value in [
        (0, 'Объект', 'retail'), (0, 'Операция', 'transport'),
        (1, 'Груз или объект операции', 'Паллеты'),
        (2, 'Объём в сутки, паллет или м²', '220'),
        (3, 'Смен в сутки', '2'), (3, 'Часов в смене', '8'),
        (3, 'Рабочих дней в году', '250'),
        (4, 'Плечо маршрута, м', '120'),
        (4, 'Сколько паллет (или иных единиц груза) робот перевозит за один рейс?', '1'),
        (4, 'Название зоны', 'Зона А'),
        (5, 'Сотрудников сейчас', '8'), (5, 'Зарплата gross, ₽/чел./мес.', '75000'),
    ]:
        interview_field(step, label, value)
    assert not js("[...document.querySelectorAll('.assistant-draft button')].find(e=>e.textContent.includes('Перенести подтверждённые поля'))?.disabled"), js("document.querySelector('.assistant-draft').innerText.slice(-1000)")
    assert click_text('.assistant-draft button', 'Перенести подтверждённые поля в расчёт')
    until("location.hash === '#calculation'")
    assert js("document.querySelector('[aria-label=\"Процессы и роли\"]').textContent.includes('Зона А')")
    assert js("(() => {const row=[...document.querySelectorAll('[aria-label=\"Процессы и роли\"] input[id^=active-]')].find(e=>e.checked)?.closest('section'); const button=row?.querySelector('button[aria-expanded]'); if(!button)return false;button.click();return true})()")
    until("[...document.querySelectorAll('[aria-label=\"Процессы и роли\"] label')].some(e=>e.textContent.includes('за один рейс'))")
    assert js("[...document.querySelectorAll('[aria-label=\"Процессы и роли\"] label')].find(e=>e.textContent.includes('за один рейс'))?.querySelector('input')?.value === '1'")
    assert click_text('[aria-label="Процессы и роли"] button', 'Проверить ввод')
    until("Boolean(document.querySelector('[aria-label=\"Предварительный расчёт\"]'))")
    until("document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] select')[1]?.options.length > 1")
    assert js("(() => {const e=document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] select')[1]; if(!e||e.options.length<2)return false; e.value=e.options[1].value; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value})()")
    assert js("(() => {const label=[...document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] label')].find(e=>e.textContent.includes('Погрузка + выгрузка')); const input=label?.querySelector('input'); if(!input)return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'90'); input.dispatchEvent(new Event('input',{bubbles:true})); return true})()")
    assert click_text('[aria-label="Предварительный расчёт"] label', 'Подтверждаю, что данные типового объекта')
    own_state = js("(() => {const box=document.querySelector('[aria-label=\"Предварительный расчёт\"] input[type=checkbox]'); const button=[...document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] button')].find(e=>e.textContent.includes('Рассчитать и сохранить')); return [box?.checked,button?.disabled,[...document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] select')].map(e=>e.value)]})()")
    assert own_state[:2] == [True, False], own_state
    assert click_text('[aria-label="Предварительный расчёт"] button', 'Рассчитать и сохранить')
    until("Boolean(document.querySelector('.capacity-results-v2'))", 30)
    until("Boolean(document.querySelector('form.economics-inputs-v2'))")
    check_plain_presentation('economics inputs')
    screenshot('economics-form')
    assert click_text('form.economics-inputs-v2 button', 'Полный расчёт')
    assert js("document.activeElement?.id === 'economics-condition-grossConfirm'")
    assert js("document.querySelector('form.economics-inputs-v2 [role=alert]')?.textContent.includes('пять условий')")
    assert click_text('form.economics-inputs-v2 button', 'Сохранить частичный результат')
    until("Boolean(document.querySelector('[aria-label=\"Частичный результат экономики\"]'))", 30)
    assert js("document.querySelector('[aria-label=\"Частичный результат экономики\"]').textContent.includes('денежный эффект отмечены «не рассчитано»')")
    check_plain_presentation('partial result')
    screenshot('partial-result')
    print('PASS: confirmed own warehouse inputs, saved C11 and honest partial economics', flush=True)

    assert click_text('details summary', 'Изменить допущение и создать новый расчёт')
    until("Boolean(document.querySelector('details form.economics-inputs-v2'))")
    assert fill('details #economics-start_seconds_from_midnight', '32400')
    assert fill('details #economics-timezone', 'Europe/Moscow')
    assert click_text('details form.economics-inputs-v2 button', 'Сохранить частичный результат')
    until("Boolean(document.querySelector('.technical-visualization .simulation-run-box'))", 30)
    assert click_text('.technical-visualization .simulation-run-box button', 'Запустить расчёт симуляции')
    until("Boolean(document.querySelector('.technical-visualization .simulation-kpis'))", 90)
    assert js("Boolean(document.querySelector('.technical-visualization .warehouse-2d-plan') || document.querySelector('.technical-visualization .simulation-canvas-wrap svg'))")
    assert js("Boolean(document.querySelector('.technical-visualization .robcraft-frame iframe'))")
    check_plain_presentation('partial simulation')
    print('PASS: own technical result reaches saved C23, 2D and 3D', flush=True)
    screenshot('simulation')

    assert click_nav('.app-nav button', 'Главная')
    until("Boolean(document.querySelector('.onboarding-screen'))")
    assert click_text('.landing-context-grid button', 'Склад')
    until("Boolean(document.querySelector('[aria-label=\"Процессы и роли\"]'))")
    assert click_text('[aria-label="Процессы и роли"] button', 'Загрузить типовой склад организаторов')
    assert click_text('[aria-label="Процессы и роли"] button', 'Открыть')
    assert click_text('[aria-label="Процессы и роли"] label', 'Подтверждаю допущение: 1 паллета за рейс')
    assert click_text('[aria-label="Процессы и роли"] label', 'Подтверждаю это допущение')
    until("!document.querySelector('[aria-label=\"Процессы и роли\"]').innerText.includes('Исправьте обязательные поля')")
    assert click_text('[aria-label="Процессы и роли"] button', 'Проверить ввод')
    until("Boolean(document.querySelector('[aria-label=\"Предварительный расчёт\"]'))")
    until("document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] select')[1]?.options.length > 1")
    assert js("(() => {const e=document.querySelectorAll('[aria-label=\"Предварительный расчёт\"] select')[1]; if(!e||e.options.length<2)return false; e.value=e.options[1].value; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value})()")
    assert click_text('[aria-label="Предварительный расчёт"] label', 'Подтверждаю, что данные типового объекта')
    assert click_text('[aria-label="Предварительный расчёт"] button', 'Рассчитать и сохранить')
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
        expression = """(() => {const title=[...document.querySelectorAll('.economics-inputs-v2 strong')].find(e=>e.textContent.startsWith(%s)); const el=title?.parentElement?.querySelector('input[type=text]'); if(!el)return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,%s); el.dispatchEvent(new Event('input',{bubbles:true})); return true})()""" % (json.dumps(label), json.dumps(value))
        assert js(expression), label
    assert fill('.economics-inputs-v2 input[placeholder="Например, Europe/Moscow"]', 'Europe/Moscow')
    assert js("(() => {const e=[...document.querySelectorAll('.economics-inputs-v2 label')].find(x=>x.textContent.includes('Кто оплачивает инфраструктуру')).querySelector('select'); e.value='VENDOR'; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value})()")
    assert js("(() => {const boxes=[...document.querySelectorAll('.economics-inputs-v2 input[type=checkbox]')]; boxes.forEach(x=>x.click()); return boxes.length})()") >= 5
    assert click_text('.economics-inputs-v2 button', 'Полный расчёт')
    until("Boolean(document.querySelector('.commercial-visualization'))", 30)
    assert js("document.querySelector('.commercial-scenario-section').textContent.includes('Сценарии')")
    until("document.querySelector('.evidence-export-v2')?.textContent.includes('Сценарии: данные доступны')")
    check_plain_presentation('full economics')
    check_mobile_width()
    print('PASS: immutable economics v2 and six scenarios', flush=True)
    screenshot('full-result')

    assert click_text('.simulation-run-box button', 'Запустить расчёт симуляции')
    until("Boolean(document.querySelector('.simulation-kpis'))", 90)
    assert js("Boolean(document.querySelector('.robcraft-frame iframe'))")
    until("document.querySelector('.robcraft-frame iframe')?.contentDocument?.readyState === 'complete'", 30)
    assert js("!document.querySelector('.robcraft-frame').textContent.includes('3D-сцена недоступна')")
    assert js("Boolean(document.querySelector('.warehouse-2d-plan') || document.querySelector('.simulation-canvas-wrap svg'))")
    check_plain_presentation('full simulation')
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
    assert pdfs[0].name.startswith('Рободовод, отчёт от ')
    assert zips[0].name.startswith('Рободовод, архив расчёта от ')
    assert 'РОБОДОВОД' in '\n'.join(page.extract_text() for page in PdfReader(pdfs[0]).pages)
    with zipfile.ZipFile(zips[0]) as archive:
        assert archive.testzip() is None
        assert {'НАЧНИТЕ_ЗДЕСЬ.md', 'Отчёт_Рободовод.pdf', 'manifest.json'} <= set(archive.namelist())
        assert archive.read('Отчёт_Рободовод.pdf') == pdfs[0].read_bytes()
        embedded_manifest = json.loads(archive.read('manifest.json'))
    run_id = embedded_manifest['run_id']
    project_id = js("fetch('/api/projects',{credentials:'include'}).then(r=>r.json()).then(p=>p.items[0].id)")
    base = f'/api/projects/{project_id}/analysis-runs/{run_id}'
    authoritative = js("""(async () => {const base=%s; const [run,manifest,report]=await Promise.all([
      fetch(base,{credentials:'include'}),fetch(base+'/exports/manifest',{credentials:'include'}),
      fetch(base+'/exports/report.pdf',{credentials:'include'})]);
      const bytes=await report.arrayBuffer(); const hash=await crypto.subtle.digest('SHA-256',bytes);
      return {run:await run.json(),manifest:await manifest.json(),report_status:report.status,
        report_source_digest:report.headers.get('X-Report-Source-Digest'),
        pdf_sha256:[...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('')};})()""" % json.dumps(base))
    assert authoritative['report_status'] == 200
    assert authoritative['run']['id'] == run_id
    assert authoritative['manifest'] == embedded_manifest
    assert authoritative['report_source_digest'] == embedded_manifest['source_snapshot_digests']['result']
    assert authoritative['pdf_sha256'] == hashlib.sha256(pdfs[0].read_bytes()).hexdigest()
    print('PASS: Chrome PDF/ZIP exactly match immutable run export and source digest', flush=True)
    call("Page.navigate", {"url": f"http://127.0.0.1:5173/api/projects/{project_id}/analysis-runs/{run_id}/exports/report-preview.pdf#zoom=125&navpanes=0"})
    time.sleep(1)
    screenshot('pdf-preview')
    call("Page.navigate", {"url": "http://127.0.0.1:5173/#projects"})
    until("Boolean(document.querySelector('.project-card'))")

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
    screenshot('saved-result')
    assert click_nav('.nav-secondary button', 'Библиотека решений')
    if not SKIP_CATALOG_MEDIA:
        until("Boolean(document.querySelector('.catalog-card img')?.naturalWidth > 0)")
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    assert click_nav('.app-nav button', 'Процесс')
    until("Boolean(document.querySelector('#assistant-query'))")
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    print('PASS: mobile 390px result, catalog and assistant', flush=True)
    screenshot('assistant')
finally:
    if ws:
        ws.close()
    chrome.terminate()
    try:
        chrome.wait(timeout=5)
    except subprocess.TimeoutExpired:
        chrome.kill()
