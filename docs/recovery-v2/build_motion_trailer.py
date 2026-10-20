"""Record WebGL/2D playback from local FastAPI route-preview without a mocked POST.

Route-only endpoints verify geometry, not an activated catalog robot or economics.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import websocket
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "frontend/public/demo/trailer"
EVIDENCE = ROOT / "docs/recovery-v2/evidence"
FONT = ROOT / "backend/calculation/assets/DejaVuSans.ttf"
FPS = 10
DURATION = 6
SCENES = (("warehouse", "СКЛАД", "Внутренняя логистика"),
          ("airport", "АЭРОПОРТ", "Багаж и наземная логистика"),
          ("clinic", "КЛИНИКА", "Внутрибольничная доставка"))
CHAPTERS = tuple((kind, title, subtitle, view) for kind, title, subtitle in SCENES
                 for view in ("3D", "2D"))


class Browser:
    def __init__(self):
        pages = requests.get("http://127.0.0.1:9225/json/list", timeout=5).json()
        page = next(p for p in pages if p.get("type") == "page"
                    and "/qa/recovery/index.html" in p.get("url", ""))
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15,
                                              suppress_origin=True)
        self.sequence = 0
        self.responses = []
        self.call("Network.enable")
        self.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900,
                  "deviceScaleFactor": 1, "mobile": False})

    def call(self, method, params=None):
        self.sequence += 1
        request_id = self.sequence
        self.ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("method") == "Network.responseReceived":
                event = response["params"]["response"]
                if "/api/v2/" in event["url"]:
                    self.responses.append({"path": event["url"].split("/api/v2/", 1)[1],
                                           "status": event["status"]})
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return result["result"].get("value")

    def screenshot(self):
        encoded = self.call("Page.captureScreenshot", {"format": "png",
                            "captureBeyondViewport": False})["data"]
        return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")


def crop(image, box):
    x, y, w, h = box
    return image.crop((round(x), round(y), round(x+w), round(y+h)))


def compose(image, geometry, title, subtitle, view, pose, frame_no):
    stage = crop(image, geometry["stage"])
    plan = crop(image, geometry["plan"])
    main, inset = (stage, plan) if view == "3D" else (plan, stage)
    canvas = Image.new("RGB", (1280, 720), "#07131e")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((26, 22, 1254, 698), radius=24, fill="#102231", outline="#2d5366", width=2)
    main_scale = min(900 / main.width, 545 / main.height)
    main = main.resize((round(main.width * main_scale), round(main.height * main_scale)),
                       Image.Resampling.LANCZOS)
    canvas.paste(main, (47+(900-main.width)//2, 100+(545-main.height)//2))
    draw.rounded_rectangle((967, 104, 1229, 330), radius=12, fill="#dfebec")
    inset.thumbnail((252, 210), Image.Resampling.LANCZOS)
    canvas.paste(inset, (972+(252-inset.width)//2, 111+(210-inset.height)//2))
    draw.text((49, 36), f"РОБОДОВОД  /  {title}  /  {view}",
              font=ImageFont.truetype(FONT, 31), fill="#f3fbfa")
    draw.text((970, 348), f"{'2D-план' if view == '3D' else '3D-сцена'} · тот же маршрут",
              font=ImageFont.truetype(FONT, 17), fill="#b1d9e6")
    draw.text((970, 405), subtitle, font=ImageFont.truetype(FONT, 17), fill="#e3f3f2")
    draw.text((970, 460), f"Поза: {pose or 'ожидание'}", font=ImageFont.truetype(FONT, 15), fill="#8fdad5")
    draw.text((49, 661), "Локальная демо-сцена · маршрут FastAPI · каталожная модель и деньги не подтверждены",
              font=ImageFont.truetype(FONT, 15), fill="#a9c4cd")
    draw.rectangle((49, 642, 49 + round(1170*(frame_no+1)/(FPS*DURATION*len(CHAPTERS))), 645), fill="#53d4c1")
    return canvas


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "frames").mkdir(exist_ok=True)
    browser = Browser()
    poses = {}
    try:
        with tempfile.TemporaryDirectory(prefix="robodovod-motion-") as tmp:
            frames = Path(tmp)
            count = 0
            for chapter_index, (kind, title, subtitle, view) in enumerate(CHAPTERS, 1):
                browser.call("Page.navigate", {"url":
                             f"http://127.0.0.1:4175/qa/recovery/index.html?kind={kind}&api=real"})
                deadline = time.monotonic()+30
                while time.monotonic() < deadline:
                    if browser.evaluate("document.querySelector('[data-glb-status]')?.dataset.glbStatus") == "READY" \
                            and browser.evaluate("document.querySelector('[data-floor-texture-status]')?.dataset.floorTextureStatus") == "READY" \
                            and browser.evaluate("new URLSearchParams(location.search).get('kind')") == kind \
                            and browser.evaluate("Boolean(document.querySelector('.scene-sim-controls button[type=submit]'))"):
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError(f"{kind}: 3D assets did not load")
                browser.evaluate("document.querySelector('.scene-sim-controls button[type=submit]').click()")
                deadline = time.monotonic()+10
                while time.monotonic() < deadline:
                    if browser.evaluate("Boolean(document.querySelector('.scene-playback-controls'))"):
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError(f"{kind}: playback did not start")
                expected_path = ("warehouse-roles/route-preview" if kind == "warehouse"
                                 else f"object-roles/{kind.upper()}/route-preview")
                if not any(row["path"] == expected_path and row["status"] == 200
                           for row in browser.responses):
                    raise RuntimeError(f"{kind}: no successful local FastAPI route-preview")
                browser.evaluate("document.querySelector('.scene-preview')?.scrollIntoView({block:'center'})")
                time.sleep(.25)
                geometry = browser.evaluate("JSON.stringify(Object.fromEntries([['stage','.scene-preview-canvas'],['plan','.scene-preview-plan .scene-preview-svg']].map(([name, selector]) => {const r=document.querySelector(selector).getBoundingClientRect();return [name,[r.x,r.y,r.width,r.height]]})))")
                geometry = json.loads(geometry)
                scene_poses = []
                next_frame = time.monotonic()
                for scene_frame in range(FPS*DURATION):
                    pose = browser.evaluate("document.querySelector('#recovery-pose')?.textContent")
                    scene_poses.append(pose)
                    frame = compose(browser.screenshot(), geometry, title, subtitle, view, pose, count)
                    frame.save(frames / f"frame-{count:04d}.png", optimize=False)
                    if scene_frame == FPS:
                        frame.save(OUTPUT / "frames" / f"chapter-{chapter_index}.jpg", quality=85)
                    if count == 12:
                        frame.save(OUTPUT / "robodovod-trailer-poster.jpg", quality=88)
                    count += 1
                    next_frame += 1/FPS
                    if next_frame > time.monotonic():
                        time.sleep(next_frame-time.monotonic())
                poses[f"{kind}-{view.lower()}"] = {"first": scene_poses[0], "last": scene_poses[-1],
                                                   "distinct": len(set(scene_poses))}
                if poses[f"{kind}-{view.lower()}"]["distinct"] < 3:
                    raise RuntimeError(f"{kind} {view}: robot did not visibly move")
                print(f"{kind} {view}: {poses[f'{kind}-{view.lower()}']}", flush=True)
            master = OUTPUT / "robodovod-trailer-master-1080p.mp4"
            web = OUTPUT / "robodovod-trailer-web-720p.mp4"
            preview = OUTPUT / "robodovod-trailer-preview-720p.mp4"
            base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-framerate", str(FPS), "-i", str(frames / "frame-%04d.png")]
            subprocess.run([*base, "-vf", "scale=1920:1080:flags=lanczos,fps=30", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", "-an", str(master)], check=True)
            subprocess.run([*base, "-vf", "fps=30", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            "-an", str(web)], check=True)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(web),
                            "-c", "copy", str(preview)], check=True)
    finally:
        browser.ws.close()
    vtt = ["WEBVTT", ""]
    for index, (_, title, subtitle, view) in enumerate(CHAPTERS):
        start, end = index*DURATION, (index+1)*DURATION
        vtt += [f"00:00:{start:02d}.000 --> 00:00:{end:02d}.000",
                f"{title}, {view}. {subtitle}. Маршрут рассчитан локальным FastAPI без подтверждения каталожной модели.", ""]
    (OUTPUT / "robodovod-trailer.ru.vtt").write_text("\n".join(vtt), encoding="utf-8")
    manifest = {"status": "LOCAL_FASTAPI_ROUTE_PREVIEW_NO_CATALOG", "audio": "NONE_SILENT",
                "duration_s": DURATION*len(CHAPTERS), "fps_capture": FPS,
                "chapters": [{"scene": kind, "view": view, "start_s": index*DURATION}
                             for index, (kind, _, _, view) in enumerate(CHAPTERS)],
                "scene_asset_manifest": "scene-assets/recovery-manifest.json",
                "master": master.name, "web": web.name, "preview": preview.name,
                "api_responses": browser.responses,
                "poses": poses,
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (master, web, preview)}}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Motion trailer: {master.stat().st_size} bytes master, {web.stat().st_size} bytes web")


if __name__ == "__main__":
    main()
