"""Five-step browser smoke against disposable PostgreSQL and real local FastAPI.

Requires Vite 4177 -> FastAPI 8001 -> seeded PostgreSQL 55432. No API mocks.
This confirms only the local activated bundle, not production deployment.
"""

import base64
import io
import json
import sys
import time
from pathlib import Path

import requests
import websocket
from pypdf import PdfReader


OUT = Path(__file__).resolve().parent / "evidence"
URL = "http://127.0.0.1:4177/"
CASES = (("retail", "Оператор погрузчика", "warehouse"),
         ("airport", "Оператор тележек", "airport"),
         ("clinic", "Транспортировщик", "clinic"))


class Browser:
    def __init__(self):
        pages = requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
        page = next(p for p in pages if p.get("type") == "page" and ":4177/" in p.get("url", ""))
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30,
                                              suppress_origin=True)
        self.seq = 0
        self.network = []
        self.pdf_requests = {}
        self.call("Network.enable")
        self.call("Page.enable")

    def call(self, method, params=None):
        self.seq += 1
        key = self.seq
        self.ws.send(json.dumps({"id": key, "method": method, "params": params or {}}))
        while True:
            data = json.loads(self.ws.recv())
            if data.get("method") == "Network.requestWillBeSent":
                request = data["params"]["request"]
                if request["url"].endswith("/report.pdf"):
                    self.pdf_requests[data["params"]["requestId"]] = request.get("postData")
            if data.get("method") == "Network.responseReceived":
                response = data["params"]["response"]
                if "/api/v2/" in response["url"]:
                    self.network.append({"url": response["url"].split("/api/v2/", 1)[1],
                                         "status": response["status"],
                                         "request_id": data["params"]["requestId"]})
            if data.get("id") == key:
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data.get("result", {})

    def js(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression,
                                                "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"].get("text", expression))
        return result["result"].get("value")

    def until(self, expression, label, seconds=50):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.js(expression):
                return
            time.sleep(.25)
        raise RuntimeError(f"{label}: {self.js('document.body.innerText.slice(-700)')}")

    def capture(self, name):
        # The DOM can be ready one frame before CSS/WebGL pixels settle.
        time.sleep(.18)
        data = self.call("Page.captureScreenshot", {"format": "png"})["data"]
        (OUT / name).write_bytes(base64.b64decode(data))

    def overflow(self, label):
        size = self.js("({viewport:innerWidth,scroll:document.documentElement.scrollWidth})")
        if size["scroll"] > size["viewport"] + 2:
            raise RuntimeError(f"{label}: horizontal overflow {size}")


def run_case(browser, width, kind, role, name, *, example=False):
    prefix = f"local-catalog-{width}-{name}" + ("-example" if example else "")
    browser.call("Page.navigate", {"url": URL})
    browser.until(f"Boolean(document.querySelector('.simple-object-{kind}'))", "home")
    browser.js("window.confirm=()=>true")
    browser.overflow(f"{prefix} home")
    if example:
        index = ("retail", "airport", "clinic").index(kind)
        browser.js(f"[...document.querySelectorAll('button')].filter(x=>x.textContent.includes('Открыть пример'))[{index}].click()")
    else:
        browser.js(f"document.querySelector('.simple-object-{kind}').click()")
    browser.until("Boolean(document.querySelector('.wr-role-toggle'))", "intake")
    if not example:
        browser.js(f"[...document.querySelectorAll('.wr-role-toggle')].find(x=>x.textContent.includes('{role}')).click()")
        browser.until("document.body.innerText.includes('Выбрано 1 из')", "role selected")
    else:
        browser.until("document.body.innerText.includes('Готовый пример')", "ready example")
    browser.overflow(f"{prefix} intake")
    browser.capture(f"{prefix}-work.png")
    submit = "[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Подобрать и рассчитать'))"
    browser.js(f"{submit}.click()")
    browser.until("document.body.innerText.includes('Предпросмотр готов')", "catalog preview", 70)
    browser.until("[...document.querySelectorAll('button')].some(x=>x.textContent.includes('Продолжить к роботам'))", "continue")
    browser.js("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Продолжить к роботам')).click()")
    browser.until("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='К симуляции')", "robots")
    browser.overflow(f"{prefix} robots")
    browser.capture(f"{prefix}-robots.png")
    browser.js("[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='К симуляции').click()")
    browser.until("Boolean(document.querySelector('.scene-sim-controls button[type=submit]'))", "simulation")
    browser.js("document.querySelector('.scene-sim-controls button[type=submit]').click()")
    browser.until("Boolean(document.querySelector('.scene-playback-controls'))", "playback", 70)
    first = browser.js("document.querySelector('[data-robot-pose]')?.getAttribute('data-robot-pose')")
    time.sleep(.65)
    second = browser.js("document.querySelector('[data-robot-pose]')?.getAttribute('data-robot-pose')")
    if not first or first == second:
        raise RuntimeError(f"{prefix}: robot did not move: {first} -> {second}")
    if example:
        browser.js("[...document.querySelectorAll('.scene-preview-mobile-switch button')].find(x=>x.textContent.includes('2D-план')).click()")
        browser.until("document.querySelector('.scene-preview-grid')?.dataset.mobileView === '2d'", "2D view")
        plan_first = browser.js("document.querySelector('.scene-preview-plan [data-robot-pose]')?.getAttribute('data-robot-pose')")
        time.sleep(.45)
        plan_second = browser.js("document.querySelector('.scene-preview-plan [data-robot-pose]')?.getAttribute('data-robot-pose')")
        if not plan_first or plan_first == plan_second:
            raise RuntimeError(f"{prefix}: 2D robot did not move: {plan_first} -> {plan_second}")
        browser.capture(f"{prefix}-2d-motion.png")
        browser.js("[...document.querySelectorAll('.scene-preview-mobile-switch button')].find(x=>x.textContent.includes('3D-сцена')).click()")
    browser.js("document.querySelector('.scene-playback-controls button').click()")
    paused = browser.js("document.querySelector('[data-robot-pose]').getAttribute('data-robot-pose')")
    time.sleep(.3)
    if paused != browser.js("document.querySelector('[data-robot-pose]').getAttribute('data-robot-pose')"):
        raise RuntimeError(f"{prefix}: pause changed pose")
    browser.js("document.querySelector('.scene-preview')?.scrollIntoView({block:'start'})")
    browser.overflow(f"{prefix} simulation")
    browser.capture(f"{prefix}-simulation.png")
    sim_text = browser.js("document.querySelector('.scene-sim-controls')?.innerText.slice(-950)")
    if example and browser.js("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('К экономике с этим ограничением')).disabled"):
        return {"width": width, "scene": name, "ready_example": True,
                "pose_first": first, "pose_second": second, "simulation_summary": sim_text,
                "financial_path_blocked": True,
                "reason": "No evidence-backed runtime robot in activated local catalog"}
    browser.js("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('К экономике с этим ограничением')).click()")
    browser.until("[...document.querySelectorAll('button')].some(x=>x.textContent.trim()==='К общему результату')", "money")
    browser.overflow(f"{prefix} money")
    browser.capture(f"{prefix}-money.png")
    browser.js("[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='К общему результату').click()")
    browser.until("[...document.querySelectorAll('button')].some(x=>x.textContent.includes('Скачать инвестиционный PDF'))", "results")
    browser.overflow(f"{prefix} result")
    browser.capture(f"{prefix}-result.png")
    verdict = browser.js("document.querySelector('.investment-verdict')?.textContent")
    start = len(browser.network)
    browser.js("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Скачать инвестиционный PDF')).click()")
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        browser.js("document.readyState")
        pdf = [row for row in browser.network[start:] if row["url"].endswith("/report.pdf")]
        if pdf:
            if pdf[-1]["status"] != 200:
                raise RuntimeError(f"{prefix}: PDF HTTP {pdf[-1]['status']}")
            break
        time.sleep(.2)
    else:
        raise RuntimeError(f"{prefix}: no PDF response")
    if width == 1440:
        payload = browser.pdf_requests.get(pdf[-1]["request_id"])
        if payload is None:
            payload = browser.call("Network.getRequestPostData", {"requestId": pdf[-1]["request_id"]})["postData"]
        response = requests.post(f"http://127.0.0.1:8001/api/v2/{pdf[-1]['url']}",
                                 data=payload, headers={"Content-Type": "application/json"}, timeout=40)
        if response.status_code != 200 or not response.content.startswith(b"%PDF-"):
            raise RuntimeError(f"{prefix}: replayed PDF HTTP {response.status_code}")
        (OUT / f"local-catalog-{name}.pdf").write_bytes(response.content)
        pdf_text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
        if " ".join(verdict.split()) not in " ".join(pdf_text.split()):
            raise RuntimeError(f"{prefix}: PDF and UI investment conclusion disagree")
    return {"width": width, "scene": name, "role": role, "ready_example": example, "pose_first": first,
            "pose_second": second, "simulation_summary": sim_text,
            "catalog_in_result": "organizer-catalog-v4" in browser.js("document.body.innerText"),
            "pdf_http_status": pdf[-1]["status"], "investment_conclusion": verdict}


def main():
    browser = Browser()
    results = []
    try:
        examples = "--examples" in sys.argv
        widths = (1440,) if "--pdf-only" in sys.argv or examples else (1440, 360, 390, 768)
        for width in widths:
            browser.call("Emulation.setDeviceMetricsOverride", {"width": width,
                         "height": 900 if width == 1440 else 800,
                         "deviceScaleFactor": 1, "mobile": width != 1440})
            for kind, role, name in CASES:
                result = run_case(browser, width, kind, role, name, example=examples)
                results.append(result)
                print(width, name, result["pose_first"], "->", result["pose_second"], flush=True)
    finally:
        browser.call("Emulation.clearDeviceMetricsOverride")
        browser.ws.close()
    if not examples:
        assert all(item["catalog_in_result"] for item in results)
    result_file = "local-catalog-examples.json" if "--examples" in sys.argv else "local-catalog-pdf-capture.json" if "--pdf-only" in sys.argv else "local-catalog-journey.json"
    (OUT / result_file).write_text(
        json.dumps({"source": "LOCAL_POSTGRESQL_17_PUBLISHED_BUNDLE",
                    "production_verified": False, "cases": results,
                    "api_responses": browser.network}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {len(results)} real-backend journeys", flush=True)


if __name__ == "__main__":
    main()
