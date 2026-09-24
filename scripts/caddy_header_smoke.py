"""Probe the production Caddy header rules through a disposable local proxy."""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> int:
    class Upstream(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *_args):
            pass

    with http.server.ThreadingHTTPServer(("0.0.0.0", 0), Upstream) as upstream, tempfile.TemporaryDirectory() as temp:
        thread = threading.Thread(target=upstream.serve_forever)
        thread.start()
        name = f"robodovod-caddy-smoke-{os.getpid()}"
        port = free_port()
        source = (ROOT / "infra/caddy/Caddyfile").read_text(encoding="utf-8")
        body = source.split("\nrobodovod.ru {\n", 1)[1]
        config = ":8080 {\n" + body.replace("backend:8000", f"host.docker.internal:{upstream.server_port}").replace(
            "frontend:80", f"host.docker.internal:{upstream.server_port}"
        )
        path = Path(temp) / "Caddyfile"
        path.write_text(config, encoding="utf-8")
        try:
            subprocess.run(
                ["docker", "run", "--rm", "-d", "--name", name, "-p", f"127.0.0.1:{port}:8080",
                 "-v", f"{path}:/etc/caddy/Caddyfile:ro", "caddy:2.11.4-alpine"],
                check=True, capture_output=True, text=True, timeout=20,
            )
            url = f"http://127.0.0.1:{port}"
            for _ in range(50):
                try:
                    if requests.get(url + "/", timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    time.sleep(0.1)
            else:
                raise AssertionError("local Caddy did not become ready")
            for route, xfo, ancestor in (
                ("/robcraft/", "SAMEORIGIN", "'self'"),
                ("/robcraft/index.html", "SAMEORIGIN", "'self'"),
                ("/", "DENY", "'none'"),
                ("/robcraft/assets/app.js", "DENY", "'none'"),
                ("/api/projects", "DENY", "'none'"),
            ):
                response = requests.get(url + route, timeout=3)
                assert response.status_code == 200, (route, response.status_code)
                assert response.headers.get("X-Frame-Options") == xfo, route
                assert f"frame-ancestors {ancestor}" in response.headers.get("Content-Security-Policy", ""), route
                assert "object-src 'none'" in response.headers["Content-Security-Policy"], route
            print("PASS: Caddy allows only RobCraft documents in same-origin frames")
            return 0
        finally:
            subprocess.run(["docker", "stop", name], capture_output=True, text=True, timeout=20)
            upstream.shutdown()
            thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
