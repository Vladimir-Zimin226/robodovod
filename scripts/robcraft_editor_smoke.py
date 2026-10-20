"""Headless Chrome smoke for the standalone RobCraft editor."""

import json
import base64
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
import sys
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
    env = {**os.environ, "ROBCRAFT_PORT": str(port)}
    server = subprocess.Popen(["node", "server.mjs"], cwd=ROOT / "robcraft", env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/scene-assets/pallet_rack.glb") as response:
                    assert response.status == 200 and response.read(4) == b"glTF"
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError("RobCraft scene asset server unavailable")
        with tempfile.TemporaryDirectory(prefix="robcraft-editor-", ignore_cleanup_errors=True) as profile:
            chrome = subprocess.Popen([str(CHROME), "--headless=new", "--enable-unsafe-swiftshader", "--disable-crash-reporter", "--disable-breakpad",
                "--no-first-run", "--remote-allow-origins=*", "--remote-debugging-port=0",
                f"--user-data-dir={profile}", f"http://127.0.0.1:{port}/"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                debug_file = Path(profile) / "DevToolsActivePort"
                for _ in range(120):
                    if debug_file.is_file():
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError("Chrome DevTools unavailable")
                debug_port = int(debug_file.read_text().splitlines()[0])
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json"))
                page = next(item for item in pages if item["type"] == "page")
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
                    exception = result.get("exceptionDetails")
                    if exception:
                        raise RuntimeError(exception)
                    return result.get("result", {}).get("value")

                def wait_for(expression):
                    for _ in range(120):
                        if evaluate(expression):
                            return
                        time.sleep(.1)
                    raise AssertionError(f"Timed out: {expression}; URL={evaluate('location.href')}; classes={evaluate('document.body.className')}; errors={evaluate('window.__errors')}")

                call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900,
                    "deviceScaleFactor": 1, "mobile": False})
                wait_for("Boolean(document.querySelector('#build-catalog button'))")
                evaluate("window.__errors=[]; window.addEventListener('error',e=>window.__errors.push(e.message)); document.querySelector('#initial-view').value='2d'; document.querySelector('#seed').value='EDITOR-SMOKE'; document.querySelector('#world-form').requestSubmit()")
                wait_for("document.body.classList.contains('editor-active')")
                assert evaluate("!document.querySelector('#craft-map').classList.contains('hidden')")
                assert evaluate("document.querySelectorAll('#craft-hotbar button').length") == 9
                evaluate("document.querySelector('#build-catalog [data-kind=decor]').click()")
                assert evaluate("document.querySelector('#craft-hotbar button.active').getAttribute('aria-label')") == "Слот 1: Декоративный блок"
                # Probe free map positions through the actual pointer and click handlers.
                placed = False
                for fx, fy in ((.5, .5), (.58, .5), (.43, .52), (.5, .7), (.6, .7), (.35, .7)):
                    expression = f"""(() => {{ const c=document.querySelector('#craft-map'), r=c.getBoundingClientRect(), x=r.left+r.width*{fx}, y=r.top+r.height*{fy}; c.dispatchEvent(new PointerEvent('pointermove',{{clientX:x,clientY:y,bubbles:true}})); c.dispatchEvent(new MouseEvent('click',{{clientX:x,clientY:y,bubbles:true}})); return JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty'))?.document.scenePatch.created.length || 0; }})()"""
                    if evaluate(expression):
                        placed = True
                        break
                assert placed, evaluate("document.querySelector('#editor-message').textContent")
                for fx in (.35, .42, .49, .56, .63):
                    expression = f"""(() => {{ const c=document.querySelector('#craft-map'), r=c.getBoundingClientRect(), x=r.left+r.width*{fx}, y=r.top+r.height*.43; c.dispatchEvent(new PointerEvent('pointermove',{{clientX:x,clientY:y,bubbles:true}})); c.dispatchEvent(new MouseEvent('click',{{clientX:x,clientY:y,bubbles:true}})); return true; }})()"""
                    evaluate(expression)
                count = evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.length")
                assert count >= 5, count
                if '--capture' in sys.argv:
                    output = ROOT / 'docs/planning/assets/robcraft-phase14-2d.png'
                    output.write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['data']))
                evaluate("document.querySelector('#empty-hand').click()")
                assert evaluate("document.querySelector('#empty-hand').classList.contains('active')")
                evaluate("(() => { const c=document.querySelector('#craft-map'), r=c.getBoundingClientRect(); c.dispatchEvent(new MouseEvent('click',{clientX:r.left+r.width*.49,clientY:r.top+r.height*.43,bubbles:true})); })()")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.length") == count - 1
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyZ',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.length") == count
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyY',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.length") == count - 1
                evaluate("(() => { const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2; c.dispatchEvent(new PointerEvent('pointerdown',{pointerId:2,button:0,altKey:true,clientX:x,clientY:y,bubbles:true})); c.dispatchEvent(new PointerEvent('pointermove',{pointerId:2,button:0,altKey:true,clientX:x+60,clientY:y+30,bubbles:true})); c.dispatchEvent(new PointerEvent('pointerup',{pointerId:2,button:0,altKey:true,clientX:x+60,clientY:y+30,bubbles:true})); })()")
                assert evaluate("document.querySelector('#map-pan-label').textContent") != '0,0 / 0,0 м'
                evaluate("document.querySelector('#map-zoom-in').click()")
                assert evaluate("document.querySelector('#map-zoom-label').textContent") == '125%'
                evaluate("document.querySelector('#map-fit').click()")
                assert evaluate("document.querySelector('#map-zoom-label').textContent") == '100%'
                evaluate("document.querySelector('#map-zone-start').click()")
                assert evaluate("!document.querySelector('#map-zone-actions').classList.contains('hidden')")
                evaluate("(() => { const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(); for(const [fx,fy] of [[.47,.53],[.52,.53],[.52,.58],[.47,.58]]) c.dispatchEvent(new MouseEvent('click',{clientX:r.left+r.width*fx,clientY:r.top+r.height*fy,bubbles:true})); document.querySelector('#map-zone-name').value='Зона теста'; document.querySelector('#map-zone-finish').click(); })()")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.zones[0].name") == 'Зона теста'
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyZ',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.zones.length") == 0
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyY',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.zones.length") == 1
                wall_clicks = """((points) => {const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),d=JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.base.config,s=Math.min(r.width/(d.width+8),r.height/(d.depth+8));for(const [x,z] of points)c.dispatchEvent(new MouseEvent('click',{clientX:r.left+r.width/2+x*s,clientY:r.top+r.height/2+z*s,bubbles:true}));})"""
                evaluate("document.querySelector('#map-wall-start').click()")
                evaluate(f"{wall_clicks}([[-8,-8],[0,-8],[8,-8]])")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.filter(x=>x.kind==='wall').length") == 2
                evaluate("document.querySelector('#map-wall-cancel').click();document.querySelector('#map-door-start').click()")
                evaluate(f"{wall_clicks}([[-8,8],[8,8]])")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.filter(x=>x.kind==='wall').length") == 4
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.filter(x=>x.kind==='door_frame').length") == 1
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyZ',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.filter(x=>x.kind==='door_frame').length") == 0
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyY',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.filter(x=>x.kind==='door_frame').length") == 1
                evaluate("document.querySelector('#map-wall-cancel').click()")
                evaluate("document.querySelector('#map-room-start').click()")
                evaluate(f"{wall_clicks}([[11,-4],[17,-4],[17,4],[11,4]])")
                evaluate("document.querySelector('#map-room-name').value='Тестовая комната'; document.querySelector('#map-room-finish').click()")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].name") == 'Тестовая комната'
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].wall_ids.length") == 4
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyZ',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms.length") == 0
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyY',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms.length") == 1
                evaluate("document.querySelector('#map-room-door-start').click()")
                evaluate(f"{wall_clicks}([[14,-4]])")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].doors[0].edge") == 0
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyZ',ctrlKey:true,bubbles:true}))")
                assert evaluate("!JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].doors")
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyY',ctrlKey:true,bubbles:true}))")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].doors.length") == 1
                evaluate("document.querySelector('#map-room-door-cancel').click()")
                if '--capture' in sys.argv:
                    time.sleep(.2)
                    output = ROOT / 'docs/planning/assets/robcraft-phase14-rooms-2d.png'
                    output.write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['data']))
                evaluate("document.querySelector('#view-toggle').click()")
                assert evaluate("document.querySelector('#craft-map').classList.contains('hidden')")
                time.sleep(.2)
                assert evaluate("window.__errors.length") == 0, evaluate("window.__errors")
                call("Page.reload", {"ignoreCache": True})
                wait_for("Boolean(document.querySelector('#build-catalog button'))")
                evaluate("document.querySelector('#initial-view').value='2d'; document.querySelector('#world-form').requestSubmit()")
                wait_for("document.body.classList.contains('editor-active')")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.length") >= 1
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.zones.length") == 1
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.created.filter(x=>x.kind==='door_frame').length") == 2
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].name") == 'Тестовая комната'
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-SMOKE:empty')).document.scenePatch.rooms[0].doors.length") == 1
                assert evaluate("document.querySelector('#craft-hotbar button').getAttribute('aria-label')") == "Слот 1: Декоративный блок"
                call("Page.navigate", {"url": f"http://127.0.0.1:{port}/?seed=EDITOR-3D&editorStart=empty"})
                wait_for("Boolean(document.querySelector('#build-catalog button'))")
                evaluate("document.querySelector('#initial-view').value='3d'; document.querySelector('#world-form').requestSubmit()")
                wait_for("document.body.classList.contains('editor-active')")
                evaluate("document.querySelector('#build-catalog [data-kind=pallet_rack]').click()")
                time.sleep(.3)
                evaluate("document.querySelector('#world').click()")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-3D:empty')).document.scenePatch.created.length") == 1
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:EDITOR-3D:empty')).document.scenePatch.created[0].kind") == "pallet_rack"
                if '--capture' in sys.argv:
                    time.sleep(.5)
                    output = ROOT / 'docs/planning/assets/robcraft-phase14-3d.png'
                    output.write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['data']))
                call("Page.navigate", {"url": f"http://127.0.0.1:{port}/?seed=OPERATIONAL-SMOKE&editorStart=empty"})
                wait_for("Boolean(document.querySelector('#build-catalog button'))")
                evaluate("document.querySelector('#initial-view').value='2d'; document.querySelector('#world-form').requestSubmit()")
                wait_for("document.body.classList.contains('editor-active')")
                operational_click = """((x,z,shift=false) => {const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),s=Math.min(r.width/(48+8),r.height/(38+8)),clientX=r.left+r.width/2+x*s,clientY=r.top+r.height/2+z*s;c.dispatchEvent(new PointerEvent('pointermove',{clientX,clientY,bubbles:true}));c.dispatchEvent(new MouseEvent('click',{clientX,clientY,shiftKey:shift,bubbles:true}));})"""
                for kind, x, z, role in [('charger', -10, 0, 'CHARGE'), ('painted_floor_marker', 10, 0, 'WORK'), ('station', 10, 8, 'DROPOFF')]:
                    evaluate(f"document.querySelector('#build-catalog [data-kind={kind}]').click()")
                    evaluate(f"{operational_click}({x},{z})")
                    evaluate("document.querySelector('#empty-hand').click()")
                    evaluate(f"{operational_click}({x},{z},true)")
                    assert evaluate("Boolean(document.querySelector('#entity-operational-role'))"), kind
                    evaluate(f"(() => {{const s=document.querySelector('#entity-operational-role');s.value='{role}';s.dispatchEvent(new Event('change',{{bubbles:true}}));}})()")
                ids = evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:OPERATIONAL-SMOKE:empty')).document.scenePatch.created.map(x=>x.id)")
                assert len(ids) == 3, ids
                for select_id, object_id in zip(('operational-charge', 'operational-work', 'operational-dropoff'), ids):
                    evaluate(f"(() => {{const s=document.querySelector('#{select_id}');s.value='{object_id}';s.dispatchEvent(new Event('change',{{bubbles:true}}));}})()")
                evaluate("document.querySelector('#operational-plan').click()")
                assert evaluate("document.querySelector('#operational-status').textContent.includes('Путь найден')"), evaluate("document.querySelector('#operational-status').textContent")
                evaluate("document.querySelector('#build-catalog [data-kind=pallet_amr]').click()")
                evaluate(f"{operational_click}(-10,-4)")
                evaluate("document.querySelector('#empty-hand').click()")
                robot_id = evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:OPERATIONAL-SMOKE:empty')).document.scenePatch.created.find(x=>x.kind==='pallet_amr').id")
                evaluate(f"document.querySelector('#operational-robot').value='{robot_id}'")
                evaluate("document.querySelector('#operational-payload').value='800';document.querySelector('#operational-speed').value='1.2';document.querySelector('#operational-assign').click()")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:OPERATIONAL-SMOKE:empty')).document.scenePatch.assignments.length") == 1
                assert evaluate("document.querySelector('#operational-assignment-list').textContent.includes('маршрут')")
                assert evaluate("document.querySelector('#economics-result').textContent.includes('PARTIAL')")
                evaluate("(() => {const x={staff_count:3,monthly_employer_cost:50000,workdays_year:250,hours_shift:8,human_tasks_shift:100,task_share:1,workload_day:50,realization_share:.5,robot_price:1000000,integration_cost:0,annual_service:100000,annual_energy:20000,discount_rate:.1,operation_seconds:30};for(const [k,v] of Object.entries(x))document.querySelector(`[data-economics-field=${k}]`).value=String(v);document.querySelector('#economics-apply').click()})()")
                assert evaluate("document.querySelector('#economics-result').textContent.includes('READY_SCENARIO')"), evaluate("document.querySelector('#economics-result').textContent")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:OPERATIONAL-SMOKE:empty')).document.scenePatch.economics.staff_count") == 3
                evaluate("document.querySelector('#operational-toggle').click()")
                wait_for("document.querySelector('#operational-live-status').textContent.includes('В движении')")
                live_before = evaluate("document.querySelector('#operational-live-status').textContent")
                time.sleep(.65)
                live_after = evaluate("document.querySelector('#operational-live-status').textContent")
                assert live_after != live_before, (live_before, live_after)
                evaluate("document.querySelector('[data-operational-speed=\"4\"]').click()")
                assert evaluate("document.querySelector('[data-operational-speed=\"4\"]').getAttribute('aria-pressed')") == 'true'
                evaluate("document.querySelector('#operational-follow').click()")
                assert evaluate("document.querySelector('#operational-follow').getAttribute('aria-pressed')") == 'true'
                running_2d = evaluate("document.querySelector('#operational-live-status').textContent")
                evaluate("document.querySelector('#view-toggle').click()")
                wait_for("document.querySelector('#craft-map').classList.contains('hidden')")
                time.sleep(.4)
                running_3d = evaluate("document.querySelector('#operational-live-status').textContent")
                assert running_3d != running_2d and evaluate("(window.__errors || []).length") == 0, (running_2d, running_3d, evaluate("window.__errors || []"))
                evaluate("document.querySelector('#view-toggle').click()")
                wait_for("!document.querySelector('#craft-map').classList.contains('hidden')")
                evaluate("document.querySelector('#operational-toggle').click()")
                wait_for("document.querySelector('#operational-live-status').textContent.includes('Пауза')")
                paused = evaluate("document.querySelector('#operational-live-status').textContent")
                time.sleep(.35)
                assert evaluate("document.querySelector('#operational-live-status').textContent") == paused
                evaluate("document.querySelector('#operational-follow').click(); document.querySelector('#map-fit').click()")
                initial_path = evaluate("document.querySelector('#operational-status').textContent")
                evaluate("document.querySelector('#map-wall-start').click()")
                evaluate(f"{operational_click}(0,-8);{operational_click}(0,8)")
                assert evaluate("document.querySelector('#operational-status').textContent.includes('Путь найден')"), evaluate("document.querySelector('#operational-status').textContent")
                assert evaluate("document.querySelector('#operational-status').textContent") != initial_path
                evaluate("document.querySelector('#map-wall-cancel').click()")
                if '--capture' in sys.argv:
                    evaluate("document.querySelector('#editor-panel').classList.add('hidden')")
                    time.sleep(.2)
                    output = ROOT / 'docs/planning/assets/robcraft-phase15-operational-path-2d.png'
                    output.write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['data']))
                    evaluate("document.querySelector('#editor-panel').classList.remove('hidden')")
                evaluate("document.querySelector('#map-wall-start').click()")
                evaluate(f"{operational_click}(0,-18);{operational_click}(0,18)")
                assert evaluate("document.querySelector('#operational-status').textContent.includes('Путь не построен')"), evaluate("document.querySelector('#operational-status').textContent")
                assert evaluate("document.querySelector('#operational-assignment-list').textContent.includes('ОСТАНОВЛЕН')")
                assert evaluate("document.querySelector('#economics-result').textContent.includes('ROUTE_BLOCKED')")
                evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyZ',ctrlKey:true,bubbles:true}))")
                assert evaluate("document.querySelector('#operational-status').textContent.includes('Путь найден')")
                assert evaluate("document.querySelector('#operational-assignment-list').textContent.includes('маршрут')")
                for name in ('warehouse', 'airport', 'clinic'):
                    call('Page.navigate', {'url': f'http://127.0.0.1:{port}/?seed=CAD-{name}'})
                    wait_for("Boolean(document.querySelector('#build-catalog button'))")
                    evaluate(f"document.querySelector('#seed').value='CAD-{name}';document.querySelector('#scene-start').value='cad';document.querySelector('#scene-start').dispatchEvent(new Event('change',{{bubbles:true}}));document.querySelector('#initial-view').value='2d'")
                    root_node = call('DOM.getDocument')['root']['nodeId']
                    file_node = call('DOM.querySelector', {'nodeId': root_node, 'selector': '#cad-file'})['nodeId']
                    fixture = ROOT / 'Разобрать/ROBODOVOD_CODEX_SOL6_EXECUTION_PACKAGE_2026-10-20/ROBODOVOD_CODEX_PACKAGE/03_ASSETS_READY/cad_samples' / f'{name}_sample.dxf'
                    call('DOM.setFileInputFiles', {'nodeId': file_node, 'files': [str(fixture)]})
                    evaluate("document.querySelector('#world-form').requestSubmit()")
                    try:
                        wait_for("document.body.classList.contains('editor-active')")
                    except AssertionError as error:
                        raise AssertionError(f"{error}; CAD={evaluate('document.querySelector(\"#cad-status\").textContent')}; error={evaluate('document.querySelector(\"#error\").textContent')}") from error
                    count = evaluate(f"JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:CAD-{name}:cad')).document.scenePatch.created.length")
                    assert count > 10, (name, count, evaluate("document.querySelector('#editor-message').textContent"))
                    assert evaluate("document.querySelector('#cad-status').textContent.includes('сегментов')")
                    evaluate("document.querySelector('#view-toggle').click()")
                    assert evaluate("document.querySelector('#craft-map').classList.contains('hidden')")
                    call('Page.reload', {'ignoreCache': True})
                    wait_for("Boolean(document.querySelector('#build-catalog button'))")
                    assert evaluate("document.querySelector('#scene-start').value") == 'cad'
                    evaluate("document.querySelector('#world-form').requestSubmit()")
                    wait_for("document.body.classList.contains('editor-active')")
                    assert evaluate(f"JSON.parse(localStorage.getItem('robcraft:scene:v1:warehouse:CAD-{name}:cad')).document.scenePatch.created.length") == count
                print("RobCraft editor browser smoke: editor, operational motion/economics, three DXF imports, 2D/3D, undo/reopen PASS")
                ws.close()
            finally:
                chrome.terminate()
                chrome.wait(timeout=5)
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
