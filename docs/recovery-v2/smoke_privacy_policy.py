"""Check the published local policy and explicit registration consent in Edge."""

import base64
import json
import time
from pathlib import Path

import requests
import websocket

BASE = "http://127.0.0.1:4177"
OUT = Path(__file__).resolve().parent / "evidence/rc-privacy-registration-390.png"


def main():
    policy = requests.get(BASE + "/privacy-policy.html", timeout=8)
    assert policy.status_code == 200
    for label in ("Зимин Владимир Андреевич", "751902969999", "325650000029609",
                  "robodovod-privacy-v1-2026-10-20", "Yandex Cloud"):
        assert label in policy.text, label
    for old in ("FLYFORECAST", "privacy-draft", "Оператор: не указан"):
        assert old not in policy.text, old

    pages = requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
    page = next(item for item in pages if item.get("type") == "page" and ":4177/" in item.get("url", ""))
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15, suppress_origin=True)
    serial = 0

    def call(method, params=None):
        nonlocal serial
        serial += 1
        current = serial
        ws.send(json.dumps({"id": current, "method": method, "params": params or {}}))
        while True:
            output = json.loads(ws.recv())
            if output.get("id") == current:
                if output.get("error"):
                    raise RuntimeError(output["error"])
                return output.get("result", {})

    def js(expression):
        return call("Runtime.evaluate", {"expression": expression,
                                         "returnByValue": True})["result"].get("value")

    try:
        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844,
                                                    "deviceScaleFactor": 1, "mobile": True})
        call("Page.navigate", {"url": BASE + "/#account"})
        for _ in range(70):
            if js("Boolean(document.querySelector('.auth-screen'))"):
                break
            time.sleep(.2)
        else:
            raise RuntimeError("registration page missing")
        js("[...document.querySelectorAll('.auth-tabs button')].find(x=>x.textContent.includes('Регистрация')).click()")
        assert js("Boolean(document.querySelector('.auth-screen a[href=\"/privacy-policy.html\"]'))")
        assert js("document.querySelector('input[type=checkbox][required]').checked") is False
        assert js("document.querySelector('input[type=checkbox][required]').required") is True
        data = call("Page.captureScreenshot", {"format": "png"})["data"]
        OUT.write_bytes(base64.b64decode(data))
        call("Page.navigate", {"url": BASE + "/privacy-policy.html"})
        for _ in range(70):
            if js("document.body?.innerText.includes('Зимин Владимир Андреевич')"):
                break
            time.sleep(.2)
        else:
            raise RuntimeError("policy page missing")
        assert js("document.documentElement.scrollWidth <= innerWidth + 2")
        data = call("Page.captureScreenshot", {"format": "png"})["data"]
        OUT.with_name("rc-privacy-policy-390.png").write_bytes(base64.b64decode(data))
        print("PASS: policy 200, operator details, current version, unchecked mobile registration consent")
    finally:
        call("Emulation.clearDeviceMetricsOverride")
        ws.close()


if __name__ == "__main__":
    main()
