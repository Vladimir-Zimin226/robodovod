"""Headless mobile touch smoke for RobCraft scene editing."""

import json
import base64
import os
import socket
import subprocess
import tempfile
import time
import sys
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    port = free_port()
    server = subprocess.Popen(["node", "server.mjs"], cwd=ROOT / "robcraft",
                              env={**os.environ, "ROBCRAFT_PORT": str(port)},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/").close()
                break
            except OSError:
                time.sleep(.1)
        with tempfile.TemporaryDirectory(prefix="robcraft-touch-", ignore_cleanup_errors=True) as profile:
            chrome = subprocess.Popen([str(CHROME), "--headless=new", "--enable-unsafe-swiftshader",
                "--disable-crash-reporter", "--disable-breakpad", "--no-first-run", "--remote-allow-origins=*",
                "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                debug_file = Path(profile) / "DevToolsActivePort"
                for _ in range(120):
                    if debug_file.is_file():
                        break
                    time.sleep(.1)
                debug_port = int(debug_file.read_text().splitlines()[0])
                page = next(item for item in json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json")) if item["type"] == "page")
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
                    if "exceptionDetails" in result:
                        raise RuntimeError(result["exceptionDetails"])
                    return result.get("result", {}).get("value")

                def wait_for(expression):
                    for _ in range(120):
                        if evaluate(expression):
                            return
                        time.sleep(.1)
                    raise AssertionError(f"Timed out: {expression}; message={evaluate('document.querySelector(\"#editor-message\")?.textContent')}")

                call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
                call("Page.navigate", {"url": f"http://127.0.0.1:{port}/?seed=TOUCH-SMOKE&editorStart=empty"})
                wait_for("Boolean(document.querySelector('#build-catalog button'))")
                assert evaluate("document.body.classList.contains('touch-mode')")
                evaluate("document.querySelector('#initial-view').value='3d'; document.querySelector('#world-form').requestSubmit()")
                wait_for("document.body.classList.contains('editor-active')")
                assert evaluate("!document.querySelector('#touch-controls').classList.contains('hidden')")
                assert evaluate("document.querySelector('#editor-panel').classList.contains('hidden')")
                evaluate("document.querySelector('#inventory-toggle').click(); [...document.querySelectorAll('.catalog-tabs button')].find(b=>b.textContent==='Декор').click(); document.querySelector('#build-catalog [data-kind=traffic_cone]').click(); document.querySelector('#inventory-toggle').click()")
                evaluate("document.querySelector('#touch-place').click()")
                wait_for("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty'))?.document.scenePatch.created.length === 1")
                first = evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created[0].position")
                evaluate("(() => { const c=document.querySelector('#world'),r=c.getBoundingClientRect(),x=r.left+r.width*.5,y=r.top+r.height*.5;c.dispatchEvent(new PointerEvent('pointerdown',{pointerId:4,pointerType:'touch',clientX:x,clientY:y,bubbles:true}));c.dispatchEvent(new PointerEvent('pointermove',{pointerId:4,pointerType:'touch',clientX:x+145,clientY:y,bubbles:true}));c.dispatchEvent(new PointerEvent('pointerup',{pointerId:4,pointerType:'touch',clientX:x+145,clientY:y,bubbles:true}));document.querySelector('#touch-place').click();})()")
                wait_for("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created.length === 2")
                second = evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created[1].position")
                assert first != second, (first, second)
                evaluate("(() => {const j=document.querySelector('#touch-joystick'),r=j.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;j.dispatchEvent(new PointerEvent('pointerdown',{pointerId:7,pointerType:'touch',clientX:x,clientY:y-35,bubbles:true}));})()")
                time.sleep(.8)
                evaluate("(() => {const j=document.querySelector('#touch-joystick');j.dispatchEvent(new PointerEvent('pointerup',{pointerId:7,pointerType:'touch',bubbles:true}));document.querySelector('#touch-place').click();})()")
                wait_for("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created.length === 3")
                third = evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created[2].position")
                assert second != third, (second, third)
                evaluate("document.querySelector('#touch-break').click()")
                wait_for("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created.length === 2")
                if '--capture' in sys.argv:
                    (ROOT / 'docs/planning/assets/robcraft-phase14-touch-3d.png').write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['data']))
                for width in (360, 390, 768):
                    call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                    assert evaluate("(() => {const ids=['#touch-joystick','#touch-place','#craft-hotbar','#craft-toolbar'];return ids.every(id=>{const r=document.querySelector(id).getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1;});})()"), width
                call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                evaluate("document.querySelector('#view-toggle').click()")
                assert evaluate("document.querySelector('#touch-controls').classList.contains('hidden')")
                evaluate("document.querySelector('#inventory-toggle').click(); document.querySelector('#craft-hotbar button').click()")
                evaluate("(() => {const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),x=r.left+r.width*.56,y=r.top+r.height*.56;c.dispatchEvent(new PointerEvent('pointerdown',{pointerId:8,pointerType:'touch',clientX:x,clientY:y,bubbles:true}));c.dispatchEvent(new PointerEvent('pointerup',{pointerId:8,pointerType:'touch',clientX:x,clientY:y,bubbles:true}));c.dispatchEvent(new MouseEvent('click',{clientX:x,clientY:y,bubbles:true}));})()")
                wait_for("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:TOUCH-SMOKE:empty')).document.scenePatch.created.length === 3")
                evaluate("(() => {const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),x=r.left+r.width*.5,y=r.top+r.height*.5;for(const [id,dx] of [[11,-30],[12,30]])c.dispatchEvent(new PointerEvent('pointerdown',{pointerId:id,pointerType:'touch',clientX:x+dx,clientY:y,bubbles:true}));c.dispatchEvent(new PointerEvent('pointermove',{pointerId:12,pointerType:'touch',clientX:x+100,clientY:y,bubbles:true}));for(const id of [11,12])c.dispatchEvent(new PointerEvent('pointerup',{pointerId:id,pointerType:'touch',bubbles:true}));})()")
                assert evaluate("document.querySelector('#map-zoom-label').textContent") != '100%'
                assert evaluate("(() => {const e=document.querySelector('#editor-toggle'),r=e.getBoundingClientRect();return document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===e;})()")
                if '--capture' in sys.argv:
                    (ROOT / 'docs/planning/assets/robcraft-phase14-touch-2d.png').write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['data']))
                for width in (360, 390, 768):
                    call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                    assert evaluate("(() => {const ids=['#craft-hotbar','#craft-toolbar','#map-controls'];return ids.every(id=>{const r=document.querySelector(id).getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1;});})()"), width
                    evaluate("document.querySelector('#inventory-toggle').click()")
                    assert evaluate("(() => {const p=document.querySelector('#editor-panel'),r=p.getBoundingClientRect(),h=document.querySelector('#craft-hotbar').getBoundingClientRect();return !p.classList.contains('hidden')&&r.left>=0&&r.right<=innerWidth&&r.bottom<=h.top;})()"), width
                    evaluate("document.querySelector('#inventory-toggle').click()")
                print("RobCraft mobile touch smoke: 3D look/move/place/break, 2D tap/pinch, 360/390/768 controls PASS")
                ws.close()
            finally:
                chrome.terminate()
                chrome.wait(timeout=5)
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
