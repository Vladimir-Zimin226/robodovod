"""Exercise native Chrome fetch and ZIP/PDF blobs against fixed API bytes.

This is a local browser transport check. PostgreSQL/API ownership and ZIP
contents are checked by the backend integration suite.
"""

from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import hashlib
from pathlib import Path
from urllib.parse import urlparse


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
    expected_zip = hashlib.sha256(package.archive).hexdigest()
    expected_pdf = hashlib.sha256(pdf).hexdigest()
    page = f"""<!doctype html><meta charset="utf-8"><p id="result">PENDING</p>
<script type="module">
import {{ EvidenceExportSession }} from '/evidenceExportApi.js';
try {{
  const saved = [];
  const session = new EvidenceExportSession({{saveImpl: (blob, filename) => saved.push([blob, filename])}});
  await session.download({json.dumps(run.project_id)}, {json.dumps(run.run_id)});
  await session.downloadReport({json.dumps(run.project_id)}, {json.dumps(run.run_id)});
  const digest = async blob => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())))
    .map(value => value.toString(16).padStart(2, '0')).join('');
  if (saved.length !== 2 || await digest(saved[0][0]) !== {json.dumps(expected_zip)} ||
      await digest(saved[1][0]) !== {json.dumps(expected_pdf)}) throw new Error('download bytes mismatch');
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
            return run_browser(server.server_port, temp, chrome)
        finally:
            server.shutdown()
            thread.join()


def run_browser(port: int, temp: str, chrome: Path) -> int:
    command = [
        str(chrome), "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--user-data-dir={Path(temp) / 'profile'}",
        "--virtual-time-budget=3000",
        "--dump-dom", f"http://127.0.0.1:{port}/",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
    if completed.returncode or '<p id="result">PASS</p>' not in completed.stdout:
        print(completed.stdout[-1000:])
        print(completed.stderr[-1000:])
        return 1
    print("PASS: native Chrome fetch; ZIP and PDF blobs match source SHA-256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
