"""Render the new Markdown user guide to printable HTML and PDF."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import websocket
from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "USER_GUIDE_2026-09-26.md"
HTML = SOURCE.with_suffix(".html")
PDF = SOURCE.with_suffix(".pdf")

STYLE = """
@page { size: A4; margin: 16mm 17mm 17mm; }
* { box-sizing: border-box; }
html { color: #18242a; background: white; font-family: Arial, 'DejaVu Sans', sans-serif; }
body { max-width: 900px; margin: auto; padding: 28px 32px; font-size: 15px; line-height: 1.52; }
h1, h2, h3 { color: #123c4a; line-height: 1.25; break-after: avoid; }
h1 { font-size: 29px; border-bottom: 4px solid #85bb46; padding-bottom: 14px; }
h2 { font-size: 21px; border-bottom: 1px solid #d6e1e4; padding-bottom: 6px; margin-top: 30px; }
h3 { font-size: 17px; margin-top: 23px; }
p, li { orphans: 2; widows: 2; }
li { margin-bottom: 5px; }
img { max-width: 100%; max-height: 500px; width: auto; height: auto; display: block;
  margin: 13px auto 4px; border: 1px solid #d6e1e4; border-radius: 5px; break-inside: avoid; }
img[src*='mobile'] { max-height: 460px; }
p:has(> img) { break-inside: avoid; }
p:has(> img) + p { font-size: 12px; color: #52636b; text-align: center; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border: 1px solid #cddadd; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #edf4f0; }
tr { break-inside: avoid; }
code { background: #e9f0f0; padding: 1px 3px; }
a { color: #09697c; }
@media print { body { max-width: none; padding: 0; font-size: 10pt; line-height: 1.38; }
  h1 { font-size: 21pt; } h2 { font-size: 15pt; margin-top: 19pt; } h3 { font-size: 12pt; }
  img { max-height: 118mm; } img[src*='mobile'] { max-height: 100mm; }
  p:has(> img) + p { font-size: 8.5pt; } table { font-size: 8.5pt; }
}
"""


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    body = MarkdownIt("default", {"html": False}).render(source)
    HTML.write_text(
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>РОБОДОВОД — руководство по новой версии</title><style>{STYLE}</style>'
        f'</head><body>{body}</body></html>', encoding="utf-8",
    )
    profile = Path(tempfile.mkdtemp(prefix="stage12-guide-pdf-", dir=ROOT / ".tmp"))
    chrome = subprocess.Popen(
        [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new", "--disable-gpu",
         "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
         "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    ws = None
    try:
        active = profile / "DevToolsActivePort"
        for _ in range(80):
            if active.exists():
                break
            time.sleep(.2)
        assert active.exists(), "Chrome did not start"
        port = active.read_text().splitlines()[0]
        pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=4).json()
        ws = websocket.create_connection(next(item["webSocketDebuggerUrl"] for item in pages if item["type"] == "page"), timeout=10)
        sequence = 0

        def call(method: str, params: dict | None = None) -> dict:
            nonlocal sequence
            sequence += 1
            ws.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
            while True:
                response = json.loads(ws.recv())
                if response.get("id") == sequence:
                    if response.get("error"):
                        raise RuntimeError(response["error"])
                    return response.get("result", {})

        call("Page.navigate", {"url": HTML.as_uri()})
        for _ in range(80):
            status = call("Runtime.evaluate", {"expression": "document.readyState === 'complete' && [...document.images].every(i => i.complete && i.naturalWidth > 0)", "returnByValue": True})
            if status.get("result", {}).get("value"):
                break
            time.sleep(.2)
        else:
            raise AssertionError("Guide images did not load")
        result = call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True})
        PDF.write_bytes(base64.b64decode(result["data"]))
        print(f"Rendered {HTML.name} and {PDF.name} ({PDF.stat().st_size} bytes)")
    finally:
        if ws:
            ws.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
