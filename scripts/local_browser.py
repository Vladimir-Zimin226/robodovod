"""Local-only Chrome CDP helper for repeatable acceptance artifacts."""
from __future__ import annotations
import base64
import json
import os
import subprocess
import time
from pathlib import Path

import requests
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parents[1]


class LocalBrowser:
    def __init__(self, url: str, output: Path, *, software_gpu=False):
        if not url.startswith('http://127.0.0.1:'):
            raise ValueError('Acceptance browser only opens localhost')
        output.mkdir(parents=True, exist_ok=True)
        self.output = output
        self.profile = output / f'chrome-{time.time_ns()}'
        command = [os.getenv('CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            '--headless=new', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
            '--remote-allow-origins=*', f'--user-data-dir={self.profile}', url]
        if software_gpu:
            command += ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        else:
            command += ['--disable-gpu']
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 20
        while not (self.profile / 'DevToolsActivePort').exists():
            if time.monotonic() >= deadline:
                self.close(); raise TimeoutError('Chrome did not start')
            time.sleep(.1)
        port = (self.profile / 'DevToolsActivePort').read_text().splitlines()[0]
        self.endpoint = f'http://127.0.0.1:{port}'
        tab = next(item for item in requests.get(self.endpoint + '/json', timeout=5).json() if item['type'] == 'page')
        self.ws = connect(tab['webSocketDebuggerUrl'], open_timeout=30, max_size=64 * 1024 * 1024)
        self.identity = 0

    def call(self, method, params=None):
        self.identity += 1
        self.ws.send(json.dumps({'id': self.identity, 'method': method, 'params': params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get('id') == self.identity:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response.get('result', {})

    def js(self, expression):
        response = self.call('Runtime.evaluate', {'expression': expression, 'awaitPromise': True, 'returnByValue': True})
        if 'exceptionDetails' in response:
            raise AssertionError(response['exceptionDetails'])
        return response.get('result', {}).get('value')

    def until(self, expression, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.js(expression)
            if value:
                return value
            time.sleep(.1)
        raise AssertionError((expression, self.js('document.body.innerText.slice(-2000)')))

    def viewport(self, width, zoom=1):
        self.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1000,
            'deviceScaleFactor': 1, 'mobile': False})
        self.js(f'document.documentElement.style.zoom={zoom}')

    def screenshot(self, name):
        self.output.joinpath(name).write_bytes(base64.b64decode(self.call('Page.captureScreenshot', {'format': 'png'})['data']))

    def close(self):
        if hasattr(self, 'ws'):
            try:
                self.call('Browser.close')
            except (OSError, RuntimeError, ConnectionClosed):
                pass
            self.ws.close()
        if hasattr(self, 'process'):
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate(); self.process.wait(timeout=5)
