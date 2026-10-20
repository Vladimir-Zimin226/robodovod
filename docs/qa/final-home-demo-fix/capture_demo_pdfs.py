"""Save and inspect PDF from real local FastAPI with the activated catalog.

The input is built by the same frontend function as the locked demo. The local
HTTP server below only serves saved PDFs to Chromium's PDF viewer for capture.
"""

import base64
import json
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recovery-v2"))
from smoke_local_catalog_journey import Browser  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from calculation.role_report import role_report_pdf  # noqa: E402
from calculation.role_report_view import build_role_report_view  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "evidence"
OUT.mkdir(exist_ok=True)
API = "http://127.0.0.1:8001"


def show_page(browser, number):
    browser.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 633, "y": 20,
                 "button": "left", "clickCount": 1})
    browser.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 633, "y": 20,
                 "button": "left", "clickCount": 1})
    browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2})
    browser.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2})
    browser.call("Input.insertText", {"text": str(number)})
    browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    browser.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    time.sleep(0.7)


def main():
    browser = Browser()
    browser.call("Page.bringToFront")
    browser.call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 1500,
                 "deviceScaleFactor": 1, "mobile": False})
    browser.call("Page.navigate", {"url": "http://127.0.0.1:4177/"})
    browser.until("Boolean(document.querySelector('.simple-demo-grid'))", "home")
    findings = []
    for object_type, kind in (("retail", "WAREHOUSE"), ("airport", "AIRPORT"), ("clinic", "CLINIC")):
        expression = ("(async () => { const {buildShowcaseInput} = await import('/src/showcasePresets.js'); "
                      f"return buildShowcaseInput({json.dumps(object_type)}); }})()")
        result = browser.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        payload = result["result"]["value"]
        preview = requests.post(f"{API}/api/v2/object-roles/{kind}/preview", json=payload, timeout=60)
        preview.raise_for_status()
        report = preview.json()
        # The already-running local API may still be using the prior Python image.
        # Rebuild only the report projection/render with current source and its real
        # activated-catalog preview; the changed endpoint is covered by TestClient.
        report["report_view"] = build_role_report_view(report)
        pdf_bytes = role_report_pdf(report)
        pdf = OUT / f"demo-{object_type}.pdf"
        pdf.write_bytes(pdf_bytes)
        pages = PdfReader(BytesIO(pdf_bytes)).pages
        if not pages or any(not page.extract_text().strip() for page in pages):
            raise AssertionError(f"{kind}: blank PDF page")
        findings.append({"kind": kind, "catalog_version": report["catalog_version"],
                         "npv_purchase_rub": report["report_view"]["economics"]["purchase"]["npv_rub"],
                         "raas_year1_expense_rub": report["report_view"]["economics"]["raas"]["annual_operating_cost_rub"],
                         "pdf_pages": len(pages), "pdf_bytes": len(pdf_bytes),
                         "render_source": "current source renderer + active local catalog preview"})

    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 4176), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for item in findings:
            object_type = {"WAREHOUSE": "retail", "AIRPORT": "airport", "CLINIC": "clinic"}[item["kind"]]
            browser.call("Page.navigate", {"url": f"http://127.0.0.1:4176/docs/qa/final-home-demo-fix/evidence/demo-{object_type}.pdf"})
            time.sleep(2)
            thumbs = []
            for number in range(1, item["pdf_pages"] + 1):
                show_page(browser, number)
                path = OUT / f"demo-{object_type}-page{number}.png"
                path.write_bytes(base64.b64decode(browser.call("Page.captureScreenshot", {"format": "png"})["data"]))
                image = Image.open(path).convert("RGB")
                image.thumbnail((320, 375))
                thumbs.append(image.copy())
            sheet = Image.new("RGB", (990, ((len(thumbs) + 2) // 3) * 400), "#d9dee0")
            draw = ImageDraw.Draw(sheet)
            for index, thumb in enumerate(thumbs):
                x, y = index % 3 * 330, index // 3 * 400
                sheet.paste(thumb, (x, y + 20))
                draw.text((x + 8, y + 4), f"{object_type} / {index + 1}", fill="#25323a")
            sheet.save(OUT / f"demo-{object_type}-contact.png")
            print(object_type, item["pdf_pages"], "pages", flush=True)
    finally:
        server.shutdown()
        browser.call("Emulation.clearDeviceMetricsOverride")
        browser.ws.close()
    (Path(__file__).resolve().parent / "demo-pdf-evidence.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
