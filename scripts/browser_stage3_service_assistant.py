"""Browser check for stage 3 against a disposable PostgreSQL and local servers."""

import base64
import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import requests
import websocket


ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path(tempfile.mkdtemp(prefix="stage3-chrome-", dir=ROOT / ".tmp"))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome = subprocess.Popen([
    CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--remote-allow-origins=*", "--remote-debugging-port=0", f"--user-data-dir={PROFILE}",
    "http://127.0.0.1:5173/#process",
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


def js(expression):
    result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    if result.get("exceptionDetails"):
        raise RuntimeError(result["exceptionDetails"])
    return result.get("result", {}).get("value")


def until(expression, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = js(expression)
        if value:
            return value
        time.sleep(.2)
    raise AssertionError(f"Timed out: {expression}; body={js('document.body.innerText.slice(-900)')}")


def click_text(selector, label):
    return js("""(() => {const element=[...document.querySelectorAll(%s)].find(x=>x.textContent.includes(%s));
      if(!element)return false;element.click();return true})()""" % (json.dumps(selector), json.dumps(label)))


def fill(selector, value):
    return js("""(() => {const element=document.querySelector(%s); if(!element)return false;
      const prototype=element.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(prototype,'value').set.call(element,%s);
      element.dispatchEvent(new Event('input',{bubbles:true}));return true})()""" % (json.dumps(selector), json.dumps(value)))


def screenshot(name):
    target = ROOT / ".tmp" / f"stage3-{name}.png"
    target.write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
    print(f"SCREENSHOT: {target}", flush=True)


try:
    active = PROFILE / "DevToolsActivePort"
    for _ in range(80):
        if active.exists():
            break
        time.sleep(.2)
    assert active.exists(), "Chrome did not open"
    port = active.read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=3).json()
    ws = websocket.create_connection(next(page["webSocketDebuggerUrl"] for page in pages if page["type"] == "page"), timeout=5)
    call("Emulation.setDeviceMetricsOverride", {"width": 1366, "height": 768, "deviceScaleFactor": 1, "mobile": False})
    until("location.hash === '#assistant' && Boolean(document.querySelector('#process-title'))")
    assert js("document.querySelector('#process-title').textContent === 'Помощник по сервису'")
    assert js("!document.querySelector('.assistant-draft,.assistant-catalog,.assistant-web')")
    assert js("!document.body.innerText.includes('Найти в интернете')")
    screenshot("assistant-desktop")
    assert click_text('.service-assistant-starters button', 'С чего начать')
    until("document.querySelectorAll('.assistant-turn.assistant').length === 1")
    assert js("document.querySelector('.assistant-turn.assistant').textContent.includes('Начните с демо')")
    assert fill('#assistant-query', 'Сколько стоит конкретный робот?')
    assert click_text('.assistant-form button[type=submit]', 'Отправить')
    until("document.querySelectorAll('.assistant-turn.assistant').length === 2")
    assert js("document.querySelectorAll('.assistant-turn.assistant')[1].textContent.includes('Библиотеке решений')")
    assert js("document.querySelectorAll('.assistant-turn.assistant')[1].querySelectorAll('button').length === 1")
    assert fill('#assistant-query', 'Нужен самоподписанный сертификат')
    assert click_text('.assistant-form button[type=submit]', 'Отправить')
    until("document.querySelectorAll('.assistant-turn.assistant').length === 3")
    assert js("document.querySelectorAll('.assistant-turn.assistant')[2].textContent.includes('Уточните')")
    assert click_text('.process-actions button', 'Перейти к расчёту')
    until("location.hash === '#calculation'")
    js("history.back()")
    until("location.hash === '#assistant' && document.querySelectorAll('.assistant-turn.assistant').length === 3")
    print('PASS: legacy route, service answers, unknown question, calculation link and Back', flush=True)

    call("Page.navigate", {"url": "http://127.0.0.1:5173/#account"})
    until("Boolean(document.querySelector('.auth-tabs'))")
    assert click_text('.auth-tabs button', 'Регистрация')
    email = f"stage3-{uuid.uuid4().hex[:12]}@example.com"
    assert fill('.auth-screen input[type=email]', email)
    assert fill('.auth-screen input[type=password]', 'Stage3-regression-local-2026')
    assert click_text('.auth-screen button[type=submit]', 'Создать аккаунт')
    until("Boolean(document.querySelector('[aria-label^=\"Аккаунт stage3-\"]'))")
    assert click_text('.account-actions button', 'Мои проекты')
    until("Boolean(document.querySelector('.inline-create input'))")
    assert fill('.inline-create input', 'Проект помощника')
    assert click_text('.inline-create button', 'Создать')
    until("location.hash === '' && Boolean(document.querySelector('.onboarding-screen'))")
    project_id = js("(async()=>{const r=await fetch('/api/projects',{credentials:'include'}); const d=await r.json(); return d.items.find(x=>x.name==='Проект помощника')?.id})()")
    assert project_id
    saved = js("""(async()=>{const token=decodeURIComponent(document.cookie.match(/(?:^|; )robodovod_csrf=([^;]+)/)?.[1]||'');
      const profile={schema_version:'assistant-interview-profile-v1',fields:{zone_label:{value:'Исторический черновик',source:'USER_ENTRY',evidence:'',confirmed:true}}};
      const response=await fetch('/api/assistant/projects/%s/profile',{method:'PUT',credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify(profile)});
      return response.ok})()""" % project_id)
    assert saved
    assert click_text('.app-nav button', 'Помощник по сервису')
    until("location.hash === '#assistant' && document.querySelector('.process-project')?.textContent.includes('Проект помощника')")
    assert click_text('.service-assistant-starters button', 'Почему отчёт частичный?')
    until("document.querySelectorAll('.assistant-turn.assistant').length === 1")
    unchanged = js("""(async()=>{const response=await fetch('/api/assistant/projects/%s/profile',{credentials:'include'});
      const body=await response.json();return body.profile?.fields?.zone_label?.value})()""" % project_id)
    assert unchanged == 'Исторический черновик'
    screenshot("project-desktop")
    call("Page.reload")
    until("location.hash === '#assistant' && document.querySelector('.process-project')?.textContent.includes('Проект помощника')")
    unchanged = js("""(async()=>{const response=await fetch('/api/assistant/projects/%s/profile',{credentials:'include'});
      const body=await response.json();return body.profile?.fields?.zone_label?.value})()""" % project_id)
    assert unchanged == 'Исторический черновик'
    print('PASS: project context and old interview draft preserved after reload', flush=True)

    call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
    time.sleep(.6)
    assert js("document.querySelector('.mobile-menu-button').getAttribute('aria-expanded') === 'false'")
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    js("window.scrollTo(0,0)")
    time.sleep(.2)
    screenshot("assistant-mobile-top")
    js("document.querySelector('.service-assistant-workspace').scrollIntoView()")
    time.sleep(.2)
    screenshot("assistant-mobile")
    assert js("document.querySelector('.mobile-menu-button').click() || true")
    until("document.querySelector('.mobile-menu-button').getAttribute('aria-expanded') === 'true'")
    assert click_text('.app-nav button', 'Расчёт')
    until("location.hash === '#calculation'")
    js("history.back()")
    until("location.hash === '#assistant' && document.querySelector('.process-project')?.textContent.includes('Проект помощника')")
    assert js("document.documentElement.scrollWidth <= 390"), js("document.documentElement.scrollWidth")
    print('PASS: mobile menu, Back, project and no horizontal overflow at 390 px', flush=True)
finally:
    if ws:
        ws.close()
    chrome.terminate()
    try:
        chrome.wait(timeout=5)
    except subprocess.TimeoutExpired:
        chrome.kill()
