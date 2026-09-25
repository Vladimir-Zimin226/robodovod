"""Capture stage 12 guide screens from localhost with disposable stage11_* data."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import psycopg
import requests
import websocket


ROOT = Path(__file__).resolve().parents[1]
WEB = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"
DB = os.getenv("DATABASE_URL", "")
if "127.0.0.1" not in DB or "/stage11_" not in DB:
    raise SystemExit("A disposable localhost stage11_* database is required")

ASSETS = ROOT / "docs" / "assets" / "user-guide-2026-09-26"
ASSETS.mkdir(parents=True, exist_ok=True)
profile = Path(tempfile.mkdtemp(prefix="stage12-guide-chrome-", dir=ROOT / ".tmp"))
chrome = subprocess.Popen(
    [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new", "--disable-gpu",
     "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
     "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
)
ws = None
sequence = 0


def call(method: str, params: dict | None = None) -> dict:
    global sequence
    sequence += 1
    ws.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
    while True:
        event = json.loads(ws.recv())
        if event.get("id") == sequence:
            if event.get("error"):
                raise RuntimeError(event["error"])
            return event.get("result", {})


def js(source: str):
    answer = call("Runtime.evaluate", {"expression": source, "returnByValue": True})
    if answer.get("exceptionDetails"):
        raise RuntimeError(answer["exceptionDetails"])
    return answer.get("result", {}).get("value")


def until(source: str, timeout: float = 25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if js(source):
            return
        time.sleep(.2)
    raise AssertionError(f"Timeout: {source}; {js('document.body.innerText.slice(0,500)')}")


def capture(name: str, route: str, selector: str, width: int):
    call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 844,
        "deviceScaleFactor": 1, "mobile": width == 390})
    call("Page.navigate", {"url": "about:blank"})
    until("location.href === 'about:blank'")
    call("Page.navigate", {"url": WEB + route})
    until(f"document.querySelector({json.dumps(selector)}) !== null")
    time.sleep(.6)
    assert js("document.documentElement.scrollWidth <= innerWidth + 1"), name
    target = ASSETS / f"{name}.png"
    target.write_bytes(base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"]))
    print(f"{target.name}: {width}px, {js('document.title')}", flush=True)


try:
    active = profile / "DevToolsActivePort"
    for _ in range(80):
        if active.exists():
            break
        time.sleep(.2)
    assert active.exists()
    port = active.read_text().splitlines()[0]
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=4).json()
    ws = websocket.create_connection(next(item["webSocketDebuggerUrl"] for item in pages if item["type"] == "page"), timeout=5)
    call("Runtime.enable")
    for width, label in ((1366, "desktop"), (390, "mobile")):
        capture(f"demo-{label}", "/#demo-warehouse", ".guest-demo-intro h1", width)
        if label == "mobile":
            capture("assistant-mobile", "/#assistant", "#process-title", width)
    with psycopg.connect(DB.replace("postgresql+psycopg://", "postgresql://")) as connection:
        email = connection.execute("SELECT email_normalized FROM users WHERE email_normalized LIKE 'stage31-%' ORDER BY created_at DESC LIMIT 1").fetchone()[0]
    owner = requests.Session()
    login = owner.post(f"{API}/api/auth/login", json={"email": email, "password": "Stage31-local-only-2026"}, timeout=15)
    assert login.status_code == 200, login.text
    for cookie in owner.cookies:
        call("Network.setCookie", {"name": cookie.name, "value": cookie.value, "url": WEB})
    capture("reports-mobile", "/#reports", ".reports-card", 390)
finally:
    if ws:
        ws.close()
    chrome.terminate()
    try:
        chrome.wait(timeout=5)
    except subprocess.TimeoutExpired:
        chrome.kill()
    shutil.rmtree(profile, ignore_errors=True)
