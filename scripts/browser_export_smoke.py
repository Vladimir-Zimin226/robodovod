"""Exercise native Chrome fetch and actual ZIP/PDF file saves against fixed API bytes.

This is a local browser transport check. PostgreSQL/API ownership and ZIP
contents are checked by the backend integration suite. Requires Chrome and
websocket-client in the local test environment.
"""

from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import websocket


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from calculation.evidence_export import build_evidence_export  # noqa: E402
from calculation.readable_report import build_readable_report  # noqa: E402
from scripts.build_evidence_export_contract import golden_run  # noqa: E402


def main() -> int:
    chrome = Path(os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
    if not chrome.is_file():
        raise SystemExit(f"Chrome is missing: {chrome}")
    run = golden_run()
    package = build_evidence_export(run)
    pdf, source_digest = build_readable_report(run)
    manifest = package.manifest.model_dump(mode="json")
    assert source_digest == manifest["source_snapshot_digests"]["result"]
    module = (ROOT / "frontend/src/evidenceExportApi.js").read_bytes()
    page = f"""<!doctype html><meta charset="utf-8"><p id="result">PENDING</p>
<script type="module">
import {{ EvidenceExportSession }} from '/evidenceExportApi.js';
try {{
  const session = new EvidenceExportSession();
  await session.download({json.dumps(run.project_id)}, {json.dumps(run.run_id)});
  await session.downloadReport({json.dumps(run.project_id)}, {json.dumps(run.run_id)});
  document.getElementById('result').textContent = 'PASS';
}} catch (error) {{
  document.getElementById('result').textContent = 'FAIL: ' + error;
}}
</script>""".encode("utf-8")
    manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                body, content_type, headers = page, "text/html; charset=utf-8", {}
            elif path == "/evidenceExportApi.js":
                body, content_type, headers = module, "text/javascript; charset=utf-8", {}
            elif path.endswith("/manifest"):
                body, content_type, headers = manifest_bytes, "application/json", {}
            elif path.endswith("/evidence.zip"):
                body, content_type = package.archive, "application/zip"
                headers = {"X-Export-Manifest-Digest": manifest["manifest_digest"]}
            elif path.endswith("/report.pdf"):
                body, content_type = pdf, "application/pdf"
                headers = {"X-Report-Source-Digest": source_digest}
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server, tempfile.TemporaryDirectory() as temp:
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            return run_browser(
                server.server_port, temp, chrome,
                {
                    f"robomera-evidence-{run.run_id}.zip": package.archive,
                    f"robomera-report-{run.run_id}.pdf": pdf,
                },
            )
        finally:
            server.shutdown()
            thread.join()


def cdp_call(connection, identity: int, method: str, params: dict | None = None) -> dict:
    connection.send(json.dumps({"id": identity, "method": method, "params": params or {}}))
    while True:
        message = json.loads(connection.recv())
        if message.get("id") == identity:
            if "error" in message:
                raise RuntimeError(message["error"])
            return message.get("result", {})


def run_browser(port: int, temp: str, chrome: Path, expected: dict[str, bytes]) -> int:
    profile = Path(temp) / "profile"
    downloads = Path(temp) / "downloads"
    downloads.mkdir()
    command = [
        str(chrome), "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--remote-debugging-port=0",
        "--remote-allow-origins=*", f"--user-data-dir={profile}", "about:blank",
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browser = None
    page = None
    try:
        active_port = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not active_port.is_file():
            time.sleep(0.1)
        if not active_port.is_file():
            raise RuntimeError("Chrome DevTools did not become ready")
        debug_port = active_port.read_text(encoding="utf-8").splitlines()[0]
        debugger = f"http://127.0.0.1:{debug_port}"
        browser_url = requests.get(debugger + "/json/version", timeout=3).json()["webSocketDebuggerUrl"]
        page_url = next(item["webSocketDebuggerUrl"] for item in requests.get(debugger + "/json", timeout=3).json() if item["type"] == "page")
        browser = websocket.create_connection(browser_url, timeout=5)
        page = websocket.create_connection(page_url, timeout=5)
        cdp_call(browser, 1, "Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(downloads)})
        cdp_call(page, 1, "Page.navigate", {"url": f"http://127.0.0.1:{port}/"})
        state = "PENDING"
        deadline = time.monotonic() + 15
        identity = 2
        while time.monotonic() < deadline:
            response = cdp_call(page, identity, "Runtime.evaluate", {
                "expression": "document.getElementById('result')?.textContent || 'PENDING'",
                "returnByValue": True,
            })
            identity += 1
            state = response.get("result", {}).get("value", "PENDING")
            if state != "PENDING":
                break
            time.sleep(0.1)
        if state != "PASS":
            raise AssertionError(f"browser export failed: {state}")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and any(not (downloads / name).is_file() for name in expected):
            time.sleep(0.1)
        for name, body in expected.items():
            path = downloads / name
            if not path.is_file() or path.read_bytes() != body:
                raise AssertionError(f"browser file missing or altered: {name}")
        print("PASS: native Chrome fetch; ZIP and PDF files match source bytes")
        return 0
    finally:
        if browser is not None:
            try:
                browser.send(json.dumps({"id": 2, "method": "Browser.close"}))
            except OSError:
                pass
            browser.close()
        if page is not None:
            page.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
