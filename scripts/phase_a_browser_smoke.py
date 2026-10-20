"""Local UI smoke for the five assessment screens with an in-process catalog stub.

Run after ``cd frontend && npm.cmd run build``. Requires Chrome, uvicorn and
websocket-client in the local test environment. Checks the five-screen route,
what-if interactions, report UI and guest PDF request; financial formulas live
in the role API tests.
"""

from __future__ import annotations

import json
import base64
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import uvicorn
import websocket
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from object_roles_api import create_object_roles_router  # noqa: E402
from warehouse_roles_api import create_warehouse_roles_router  # noqa: E402


CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def _catalog():
    return SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="ui-smoke"), positions=[])


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    if not CHROME.is_file():
        raise RuntimeError(f"Chrome not found: {CHROME}")
    trailer_dir = ROOT / "docs/planning/assets/trailer-frames" if "--capture-trailer" in sys.argv else None
    if trailer_dir:
        trailer_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI()
    app.include_router(create_object_roles_router(_catalog))
    app.include_router(create_warehouse_roles_router(_catalog))

    @app.get("/api/auth/me")
    def me():
        raise HTTPException(401, "authentication required")

    app.mount("/", StaticFiles(directory=ROOT / "frontend/dist", html=True))
    port = _port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix="robodovod-a-smoke-") as profile:
        chrome = subprocess.Popen([str(CHROME), "--headless=new", "--enable-unsafe-swiftshader", "--no-first-run",
            "--no-default-browser-check", "--remote-allow-origins=*", "--remote-debugging-port=0",
            f"--user-data-dir={profile}", f"http://127.0.0.1:{port}/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            debug_file = Path(profile) / "DevToolsActivePort"
            for _ in range(100):
                if debug_file.is_file():
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Chrome DevTools did not start")
            debug_port = int(debug_file.read_text().splitlines()[0])
            pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json"))
            page = next(item for item in pages if item["type"] == "page")
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20)
            counter = 0

            def call(method, params=None):
                nonlocal counter
                counter += 1
                current = counter
                ws.send(json.dumps({"id": current, "method": method, "params": params or {}}))
                while True:
                    response = json.loads(ws.recv())
                    if response.get("id") == current:
                        if "error" in response:
                            raise RuntimeError(response["error"])
                        return response.get("result", {})

            def evaluate(expression):
                result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                return result.get("result", {}).get("value")

            def wait_for(expression, timeout=12):
                until = time.monotonic() + timeout
                while time.monotonic() < until:
                    if evaluate(expression):
                        return
                    time.sleep(0.1)
                raise AssertionError(f"Timed out: {expression}; DOM: {evaluate('document.body.innerText.slice(0, 400)')}")

            def click_text(label):
                ok = evaluate(f"(() => {{ const b = [...document.querySelectorAll('button')].find(x => x.innerText.includes({json.dumps(label)})); if (b && !b.disabled) {{ b.click(); return true; }} return false; }})()")
                if not ok:
                    raise AssertionError(f"Button unavailable: {label}")

            visual_dir = ROOT / "docs/visual-polish/screenshots" if "--visual-capture" in sys.argv else None
            if visual_dir:
                visual_dir.mkdir(parents=True, exist_ok=True)

            def visual_capture(label, mobile=False, width=None):
                if not visual_dir:
                    return
                width = width or (390 if mobile else 1440)
                mobile = width <= 768
                call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900,
                    "deviceScaleFactor": 1, "mobile": mobile})
                time.sleep(.3)
                overflow = evaluate("document.documentElement.scrollWidth - window.innerWidth")
                if mobile and overflow > 2:
                    print(f"MOBILE OVERFLOW {label}: {overflow}px")
                shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                (visual_dir / f"{label}-{width}.png").write_bytes(base64.b64decode(shot["data"]))
                if mobile:
                    call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900,
                        "deviceScaleFactor": 1, "mobile": False})
                    time.sleep(.2)

            call("Page.enable")
            if visual_dir:
                call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900,
                    "deviceScaleFactor": 1, "mobile": False})
            wait_for("document.body.innerText.includes('Смотреть готовые примеры')")
            visual_capture("01-home")
            visual_capture("01-home", mobile=True)
            visual_capture("01-home", width=360)
            visual_capture("01-home", width=768)
            wait_for("document.querySelector('.trailer-preview video')?.readyState >= 2", timeout=20)
            assert evaluate("document.querySelector('.trailer-preview video').muted")
            preview_shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            (ROOT / "docs/planning/assets/phase-e-trailer-preview.png").write_bytes(base64.b64decode(preview_shot["data"]))
            click_text("Смотреть полный трейлер")
            wait_for("Boolean(document.querySelector('[role=dialog][aria-label=\"Полный трейлер сцен\"]'))")
            wait_for("document.querySelector('.trailer-dialog video')?.readyState >= 2", timeout=20)
            assert evaluate("document.querySelector('.trailer-dialog video').muted")
            full_shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            (ROOT / "docs/planning/assets/phase-e-trailer-full.png").write_bytes(base64.b64decode(full_shot["data"]))
            click_text("Пауза")
            wait_for("document.querySelector('.trailer-dialog video').paused")
            click_text("Аэропорт · 3D")
            wait_for("document.querySelector('.trailer-dialog video').currentTime >= 60")
            click_text("Стоп")
            wait_for("document.querySelector('.trailer-dialog video').currentTime === 0")
            click_text("Закрыть")
            wait_for("!document.querySelector('.trailer-dialog')")
            evaluate("document.querySelector('.trailer-preview video').dispatchEvent(new Event('error'))")
            wait_for("document.querySelectorAll('.trailer-fallback figure').length === 6")
            call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
            call("Page.navigate", {"url": f"http://127.0.0.1:{port}/"})
            wait_for("Boolean(document.querySelector('.trailer-preview video'))")
            assert evaluate("document.querySelector('.trailer-preview video').paused")
            call("Emulation.setEmulatedMedia", {"features": []})
            call("Page.navigate", {"url": f"http://127.0.0.1:{port}/"})
            wait_for("document.body.innerText.includes('Смотреть готовые примеры')")
            print("PASS trailer: muted preview, full playback, pause, chapter seek, stop")
            for index, kind in enumerate(("Склад", "Аэропорт", "Клиника")):
                if index:
                    call("Page.navigate", {"url": f"http://127.0.0.1:{port}/"})
                    wait_for("document.body.innerText.includes('Смотреть готовые примеры')")
                assert evaluate(f"(() => {{ const b = document.querySelectorAll('section[aria-label=\"Смотреть готовые примеры\"] button')[{index}]; b.click(); return true; }})()")
                wait_for("document.body.innerText.includes('ШАГ 1 ИЗ 5 · РАБОТЫ')")
                if index == 0:
                    visual_capture("02-works")
                    visual_capture("02-works", mobile=True)
                    visual_capture("02-works", width=360)
                    visual_capture("02-works", width=768)
                wait_for("[...document.querySelectorAll('button')].some(x => x.innerText.includes('Подобрать') && !x.disabled)")
                click_text("Подобрать")
                wait_for("document.body.innerText.includes('Предпросмотр готов')")
                click_text("Продолжить к роботам")
                wait_for("location.hash === '#robots'")
                if index == 0:
                    visual_capture("03-robots")
                    visual_capture("03-robots", mobile=True)
                    visual_capture("03-robots", width=360)
                    visual_capture("03-robots", width=768)
                click_text("К симуляции")
                wait_for("location.hash === '#simulation'")
                wait_for("document.querySelector('.scene-preview-canvas')?.dataset.glbStatus === 'READY'")
                visual_capture(f"04-simulation-{('warehouse', 'airport', 'clinic')[index]}")
                if index == 0:
                    visual_capture("04-simulation", mobile=True)
                    visual_capture("04-simulation", width=360)
                    visual_capture("04-simulation", width=768)
                same_geometry = evaluate("""(() => {
                    const plan = document.querySelector('.scene-preview-svg');
                    const canvas = document.querySelector('.scene-preview-canvas');
                    const ids = (selector, attr) => [...plan.querySelectorAll(selector)].map(node => node.getAttribute(attr)).sort().join(',');
                    return ids('[data-instance-id]', 'data-instance-id') === canvas.dataset.instanceIds
                        && ids('[data-zone-id]', 'data-zone-id') === canvas.dataset.zoneIds
                        && ids('[data-route-id]', 'data-route-id') === canvas.dataset.routeIds;
                })()""")
                assert same_geometry, f"Scene projections differ: {kind}"
                shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                artifact = ROOT / "docs/planning/assets" / f"phase-b-scene-{('warehouse', 'airport', 'clinic')[index]}.png"
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_bytes(base64.b64decode(shot["data"]))
                compact_width = evaluate("document.querySelector('.scene-preview-canvas').width")
                click_text("Развернуть 3D")
                wait_for("document.querySelector('.scene-preview-3d--expanded .scene-preview-canvas')?.width > " + str(compact_width))
                if trailer_dir:
                    frame = evaluate("document.querySelector('.scene-preview-3d--expanded .scene-preview-canvas').toDataURL('image/png')")
                    (trailer_dir / f"{('warehouse', 'airport', 'clinic')[index]}-3d.png").write_bytes(
                        base64.b64decode(frame.split(",", 1)[1]))
                glb_shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                (ROOT / "docs/planning/assets" / f"phase-c-glb-{('warehouse', 'airport', 'clinic')[index]}.png").write_bytes(
                    base64.b64decode(glb_shot["data"]))
                click_text("Свернуть")
                if trailer_dir:
                    frame_result = call("Runtime.evaluate", {"expression": """(async () => {
                        const svg = document.querySelector('svg[aria-label^="План сверху"]');
                        const source = new XMLSerializer().serializeToString(svg);
                        const url = URL.createObjectURL(new Blob([source], { type: 'image/svg+xml' }));
                        const image = new Image();
                        const frame = await new Promise((resolve, reject) => {
                            image.onload = () => {
                                const canvas = document.createElement('canvas');
                                canvas.width = 1920; canvas.height = 1080;
                                const context = canvas.getContext('2d');
                                context.fillStyle = '#edf4f2'; context.fillRect(0, 0, 1920, 1080);
                                const ratio = Math.min(1840 / image.width, 1000 / image.height);
                                const width = image.width * ratio, height = image.height * ratio;
                                context.drawImage(image, (1920-width)/2, (1080-height)/2, width, height);
                                resolve(canvas.toDataURL('image/png'));
                            };
                            image.onerror = reject;
                            image.src = url;
                        });
                        URL.revokeObjectURL(url);
                        return frame;
                    })()""", "returnByValue": True, "awaitPromise": True})
                    frame = frame_result["result"]["value"]
                    (trailer_dir / f"{('warehouse', 'airport', 'clinic')[index]}-2d.png").write_bytes(
                        base64.b64decode(frame.split(",", 1)[1]))
                if index == 1:
                    assert evaluate("Boolean(document.querySelector('.scene-sim-controls select'))")
                    evaluate("""(() => {
                        const select = document.querySelector('.scene-sim-controls select');
                        const option = [...select.options].find(item => item.textContent.includes('Водитель спецтехники'));
                        if (!option) throw Error('transport work missing');
                        select.value = option.value;
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                    })()""")
                    for label, value in (("Скорость с грузом", "1"), ("Скорость без груза", "1"),
                                         ("Единиц за рейс", "1"), ("Погрузка", "30"),
                                         ("Разгрузка", "30"), ("Задержка на поворотах", "5"),
                                         ("Участок: центр X", "35"), ("Участок: центр Y", "29"),
                                         ("Участок: ширина", "8"), ("Участок: длина", "2")):
                        changed = evaluate(f"""(() => {{
                            const field = [...document.querySelectorAll('.scene-sim-field')].find(node => node.textContent.includes({json.dumps(label)}));
                            if (!field) return false;
                            const input = field.querySelector('input');
                            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, {json.dumps(value)});
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return true;
                        }})()""")
                        assert changed, label
                    assert evaluate("document.querySelector('.journey-actions .primary-action').disabled")
                    click_text("Пересчитать по маршруту")
                    wait_for("document.querySelector('.scene-sim-controls [role=\"status\"]')?.innerText.includes('MODELED')")
                    wait_for("document.querySelector('.scene-preview-canvas')?.dataset.glbStatus === 'READY'")
                    assert not evaluate("document.querySelector('.journey-actions .primary-action').disabled")
                    assert evaluate("""(() => {
                        const plan = document.querySelector('.scene-preview-svg');
                        const canvas = document.querySelector('.scene-preview-canvas');
                        const ids = root => [...root.querySelectorAll('[data-route-id]')].map(node => node.dataset.routeId).sort().join(',');
                        return ids(plan) === canvas.dataset.routeIds && ids(plan) === 'sim-empty,sim-loaded'
                            && Boolean(plan.querySelector('[data-zone-id="user-shared-lane"]'))
                            && canvas.dataset.zoneIds.includes('user-shared-lane')
                            && canvas.dataset.glbStatus === 'READY';
                    })()""")
                    simulated_shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                    (ROOT / "docs/planning/assets/phase-b-scene-airport-simulated.png").write_bytes(
                        base64.b64decode(simulated_shot["data"]))
                click_text("К экономике с этим ограничением")
                wait_for("location.hash === '#money'")
                if index == 0:
                    visual_capture("05-money")
                    visual_capture("05-money", mobile=True)
                    visual_capture("05-money", width=360)
                    visual_capture("05-money", width=768)
                if index == 1:
                    wait_for("Boolean(document.querySelector('.what-if-panel .what-if-column dl'))")
                    base_before = evaluate("document.querySelector('.what-if-column').innerText")
                    for label, value in (("Цена робота", "20"), ("Объём работ", "40"),
                                         ("Скорость/выработка", "-20")):
                        changed = evaluate(f"""(() => {{
                            const field = [...document.querySelectorAll('.what-if-field')]
                                .find(node => node.textContent.includes({json.dumps(label)}));
                            if (!field) return false;
                            const input = field.querySelector('input[type="range"]');
                            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, {json.dumps(value)});
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return true;
                        }})()""")
                        assert changed, label
                    wait_for("Boolean(document.querySelectorAll('.what-if-column dl')[1])", timeout=20)
                    assert evaluate("document.querySelector('.what-if-column').innerText") == base_before
                    assert evaluate("document.querySelectorAll('.what-if-column')[1].innerText.includes('Δ')")
                    assert evaluate("document.querySelectorAll('.what-if-column')[1].innerText.includes('Маршрут:')")
                    what_if_shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                    (ROOT / "docs/planning/assets/phase-d-what-if-airport.png").write_bytes(base64.b64decode(what_if_shot["data"]))
                    click_text("Сбросить «Что если?»")
                    wait_for("document.querySelectorAll('.what-if-column dl').length === 1")
                    assert evaluate("document.querySelector('.what-if-column').innerText") == base_before
                    evaluate("""(() => {
                        const field = [...document.querySelectorAll('.what-if-field')]
                            .find(node => node.textContent.includes('Объём работ'));
                        const input = field.querySelector('input[type="range"]');
                        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '10');
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    })()""")
                    wait_for("Boolean(document.querySelectorAll('.what-if-column dl')[1])", timeout=20)
                click_text("К общему результату")
                wait_for("location.hash === '#results'")
                wait_for("document.body.innerText.includes('Скачать инвестиционный PDF')")
                if index == 0:
                    visual_capture("06-result")
                    visual_capture("06-result", mobile=True)
                    visual_capture("06-result", width=360)
                    visual_capture("06-result", width=768)
                assert evaluate("Boolean(document.querySelector('.investment-report'))")
                assert evaluate("document.querySelector('.investment-report').innerText.includes('Чувствительность к реализуемой доле ФОТ')")
                if index == 1:
                    assert evaluate("document.querySelector('.investment-report').innerText.includes('Что если?')")
                    assert evaluate("document.querySelector('.investment-report').innerText.includes('Покупка · NPV')")
                    report_shot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                    (ROOT / "docs/planning/assets/phase-d-investment-report-airport.png").write_bytes(base64.b64decode(report_shot["data"]))
                    evaluate("""(() => {
                        const originalFetch = window.fetch;
                        window.fetch = async (...args) => {
                            if (String(args[0]).includes('/report.pdf')) {
                                window.__pdfRequest = JSON.parse(args[1].body);
                                const response = await originalFetch(...args);
                                window.__pdfStatus = response.status;
                                if (response.ok) {
                                    const reader = new FileReader();
                                    reader.onload = () => { window.__pdfData = reader.result; };
                                    reader.readAsDataURL(await response.clone().blob());
                                }
                                return response;
                            }
                            return originalFetch(...args);
                        };
                    })()""")
                    click_text("Скачать инвестиционный PDF")
                    wait_for("Boolean(window.__pdfStatus)", timeout=25)
                    assert evaluate("window.__pdfStatus === 200")
                    assert evaluate("window.__pdfRequest.scene_snapshots?.two_d_png?.startsWith('data:image/png;base64,')")
                    assert evaluate("window.__pdfRequest.scene_snapshots?.three_d_png?.startsWith('data:image/png;base64,')")
                    assert evaluate("Boolean(window.__pdfRequest.what_if_input)")
                    wait_for("Boolean(window.__pdfData)", timeout=25)
                    pdf_data = evaluate("window.__pdfData")
                    (ROOT / "docs/planning/assets/phase-d-investment-report-airport.pdf").write_bytes(
                        base64.b64decode(pdf_data.split(",", 1)[1]))
                if index == 0:
                    wait_for("Boolean(document.querySelector('[role=\"dialog\"][aria-label=\"Сохранить результат\"]'))")
                else:
                    assert not evaluate("Boolean(document.querySelector('[role=\"dialog\"][aria-label=\"Сохранить результат\"]'))")
                print(f"PASS {kind}: Работа → Роботы → Симуляция → Деньги → Результат")
                if index == 0:
                    click_text("На главную")
                    wait_for("document.body.innerText.includes('Смотреть готовые примеры')")
                    evaluate("window.__confirmCalls = 0; window.confirm = () => { window.__confirmCalls++; return false; }")
                    evaluate("document.querySelectorAll('section[aria-label=\"Смотреть готовые примеры\"] button')[1].click()")
                    assert evaluate("window.__confirmCalls === 1 && location.hash === ''")
                    evaluate("window.confirm = () => true")
                    evaluate("document.querySelectorAll('section[aria-label=\"Смотреть готовые примеры\"] button')[1].click()")
                    wait_for("location.hash === '#calculation'")
                    print("PASS guest replacement: cancel preserves page; accept opens new work")
            for old_hash in ("#demo-warehouse", "#templates", "#assistant"):
                call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{old_hash}"})
                wait_for("document.body.innerText.includes('Смотреть готовые примеры')")
                assert not evaluate("document.body.innerText.includes('Насколько подробно оценивать?')")
            for private_hash, title in (("#projects", "Проекты"), ("#craft", "Конструктор объекта")):
                call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{private_hash}"})
                wait_for(f"document.body.innerText.includes({json.dumps(title)})")
                assert evaluate("document.body.innerText.includes('Для доступа войдите') || document.body.innerText.includes('Для сохранённых проектов войдите')")
            call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#account"})
            wait_for("Boolean(document.querySelector('.auth-screen'))")
            evaluate("[...document.querySelectorAll('.auth-tabs button')].find(button=>button.textContent.includes('Регистрация')).click()")
            assert evaluate("Boolean(document.querySelector('input[type=checkbox][required]'))")
            assert not evaluate("document.querySelector('input[type=checkbox][required]').checked")
            assert evaluate("document.querySelector('.auth-screen a[href=\"/privacy-policy.html\"]') !== null")
            print("PASS legacy redirects, guest private views, single save prompt")
            ws.close()
        finally:
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
