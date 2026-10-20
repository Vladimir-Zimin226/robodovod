"""Browser smoke for RobCraft project save/reopen/conflict using a same-origin API stub."""

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROJECT_ID = "01234567-89ab-4cde-8fab-0123456789ab"


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
        with tempfile.TemporaryDirectory(prefix="robcraft-project-", ignore_cleanup_errors=True) as profile:
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
                    if "exceptionDetails" in result:
                        raise RuntimeError(result["exceptionDetails"])
                    return result.get("result", {}).get("value")

                def wait_for(expression):
                    for _ in range(120):
                        if evaluate(expression):
                            return
                        time.sleep(.1)
                    raise AssertionError(f"Timed out: {expression}; status={evaluate('document.querySelector(\"#project-scene-status\")?.textContent')}")

                api = f"/api/projects/{PROJECT_ID}/robcraft-scene"
                injection = f"""(() => {{
                  const original = window.fetch.bind(window), endpoint = {json.dumps(api)}, key = 'robcraft-mock-api';
                  const reply = (status, payload) => Promise.resolve(new Response(JSON.stringify(payload), {{status, headers: {{'Content-Type':'application/json'}}}}));
                  window.fetch = (url, options={{}}) => {{
                    if (!String(url).startsWith(endpoint)) return original(url, options);
                    const state = JSON.parse(localStorage.getItem(key) || '{{"revision":0,"name":null,"versions":[]}}');
                    if (String(url).includes('/versions/')) {{
                      const number = Number(String(url).split('/').pop());
                      const version = state.versions.find(item => item.revision === number);
                      return reply(version ? 200 : 404, version || {{detail:'version not found'}});
                    }}
                    if (options.method === 'POST' && String(url).endsWith('/save-as')) {{
                      const body = JSON.parse(options.body);
                      if (body.expected_revision !== state.revision) return reply(409, {{detail:{{current_revision:state.revision}}}});
                      const project_id = '11234567-89ab-4cde-8fab-0123456789ab';
                      localStorage.setItem('robcraft-mock-copy', JSON.stringify(body.document));
                      return reply(201, {{project_id, revision:1, name:body.name, saved_at:new Date().toISOString()}});
                    }}
                    if (options.method === 'PUT') {{
                      const body = JSON.parse(options.body);
                      if (body.expected_revision !== state.revision) return reply(409, {{detail:{{current_revision:state.revision}}}});
                      const version = {{revision:state.revision+1,name:body.name,saved_at:new Date().toISOString(),document:body.document}};
                      state.revision = version.revision; state.name=version.name; state.versions.push(version);
                      localStorage.setItem(key, JSON.stringify(state));
                      return reply(200, version);
                    }}
                    return reply(200, {{revision:state.revision,name:state.name,versions:state.versions.map(item=>({{revision:item.revision,name:item.name,saved_at:item.saved_at}})),document:state.versions.at(-1)?.document || null}});
                  }};
                }})()"""
                checked = call("Runtime.evaluate", {"expression": injection, "returnByValue": True})
                assert "exceptionDetails" not in checked, checked
                call("Page.enable")
                call("Page.addScriptToEvaluateOnNewDocument", {"source": injection})
                call("Page.navigate", {"url": f"http://127.0.0.1:{port}/?project_id={PROJECT_ID}"})
                wait_for("Boolean(document.querySelector('#build-catalog button'))")
                wait_for("document.querySelector('#project-launch-status')?.textContent.includes('пока нет сцены')")
                evaluate("document.querySelector('#initial-view').value='2d'; document.querySelector('#seed').value='PROJECT-SMOKE'; document.querySelector('#world-form').requestSubmit()")
                wait_for("document.body.classList.contains('editor-active')")
                evaluate("document.querySelector('#build-catalog [data-kind=pallet_rack]').click()")
                evaluate("(() => { const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),x=r.left+r.width*.5,y=r.top+r.height*.5;c.dispatchEvent(new PointerEvent('pointermove',{clientX:x,clientY:y,bubbles:true}));c.dispatchEvent(new MouseEvent('click',{clientX:x,clientY:y,bubbles:true})); })()")
                evaluate("(() => { document.querySelector('#map-zone-start').click(); const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(); for(const [fx,fy] of [[.46,.53],[.52,.53],[.52,.59],[.46,.59]]) c.dispatchEvent(new MouseEvent('click',{clientX:r.left+r.width*fx,clientY:r.top+r.height*fy,bubbles:true})); document.querySelector('#map-zone-name').value='Приёмка'; document.querySelector('#map-zone-finish').click(); })()")
                evaluate("document.querySelector('#map-zone-list button').click()")
                evaluate("(() => { document.querySelector('#map-room-start').click(); const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),w=48,d=38,s=Math.min(r.width/(w+8),r.height/(d+8)); for(const [x,z] of [[11,-4],[17,-4],[17,4],[11,4]]) c.dispatchEvent(new MouseEvent('click',{clientX:r.left+r.width/2+x*s,clientY:r.top+r.height/2+z*s,bubbles:true})); document.querySelector('#map-room-name').value='Сборка'; document.querySelector('#map-room-finish').click(); })()")
                evaluate("(() => { document.querySelector('#map-room-door-start').click(); const c=document.querySelector('#craft-map'),r=c.getBoundingClientRect(),s=Math.min(r.width/(48+8),r.height/(38+8)); c.dispatchEvent(new MouseEvent('click',{clientX:r.left+r.width/2+14*s,clientY:r.top+r.height/2-4*s,bubbles:true})); document.querySelector('#map-room-door-cancel').click(); })()")
                evaluate("document.querySelector('[data-economics-field=staff_count]').value='3';document.querySelector('#economics-apply').click()")
                evaluate("document.querySelector('#project-scene-save').click()")
                wait_for("document.querySelector('#project-scene-status').textContent.includes('версия 1')")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.created.length") == 7
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.zones.length") == 1
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.zones[0].operational_role") == 'WORK'
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.rooms[0].name") == 'Сборка'
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.rooms[0].doors.length") == 1
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.economics.staff_count") == 3
                evaluate("window.__beforeReload = true")
                call("Page.reload", {"ignoreCache": True})
                wait_for("!window.__beforeReload && document.body.classList.contains('editor-active') && document.querySelector('#project-scene-status').textContent.includes('версия 1')")
                assert evaluate("document.querySelector('#craft-hotbar button').getAttribute('aria-label')") == "Слот 1: Паллетный стеллаж"
                assert evaluate("document.querySelector('#map-zone-list').textContent.includes('Приёмка')")
                assert evaluate("document.querySelector('#map-zone-list').textContent.includes('Снять WORK')")
                assert evaluate("document.querySelector('#map-room-list').textContent.includes('Сборка')")
                assert evaluate("document.querySelector('[data-economics-field=staff_count]').value") == '3'
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions[0].document.scenePatch.rooms[0].doors[0].edge") == 0
                evaluate("document.querySelector('#project-scene-rename').click(); document.querySelector('#project-scene-name').value='Переименованная сцена'; document.querySelector('#project-scene-name-form').requestSubmit()")
                wait_for("document.querySelector('#project-scene-status').textContent.includes('версия 2')")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).name") == "Переименованная сцена"
                evaluate("(() => { const state=JSON.parse(localStorage.getItem('robcraft-mock-api')); state.revision=3; localStorage.setItem('robcraft-mock-api',JSON.stringify(state)); document.querySelector('#project-scene-save').click(); })()")
                wait_for("document.querySelector('#project-scene-status').textContent.includes('другой вкладке')")
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-api')).versions.length") == 2
                evaluate("(() => { const state=JSON.parse(localStorage.getItem('robcraft-mock-api')); state.revision=2; localStorage.setItem('robcraft-mock-api',JSON.stringify(state)); })()")
                evaluate("document.querySelector('#project-scene-save-as').click(); document.querySelector('#project-scene-name').value='Копия склада'; document.querySelector('#project-scene-name-form').requestSubmit()")
                wait_for("document.querySelector('#project-scene-status').textContent.includes('Новый проект')")
                assert evaluate("new URLSearchParams(location.search).get('project_id')") == "11234567-89ab-4cde-8fab-0123456789ab"
                assert evaluate("JSON.parse(localStorage.getItem('robcraft-mock-copy')).scenePatch.created.length") == 7
                print("RobCraft project browser smoke: save, reopen room door and zone, rename, conflict, save as PASS")
                ws.close()
            finally:
                chrome.terminate()
                chrome.wait(timeout=5)
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
