"""Build the silent six-part trailer from actual local runtime captures.

Run ``python scripts/phase_a_browser_smoke.py --capture-trailer`` first.
Only our rendered SceneModel frames are used; no third-party music or photos.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "docs/planning/assets/trailer-frames"
OUTPUT = ROOT / "frontend/public/demo/trailer"
FONT = ROOT / "backend/calculation/assets/DejaVuSans.ttf"
SECTIONS = [
    ("warehouse", "3d", "Склад · 3D", "8 сценарных работ"),
    ("warehouse", "2d", "Склад · план 2D", "Маршрут и зоны из SceneModel"),
    ("airport", "3d", "Аэропорт · 3D", "13 сценарных работ"),
    ("airport", "2d", "Аэропорт · план 2D", "Маршрут и зоны из SceneModel"),
    ("clinic", "3d", "Клиника · 3D", "14 сценарных работ"),
    ("clinic", "2d", "Клиника · план 2D", "Маршрут и зоны из SceneModel"),
]


def prepared_frame(source: Path, target: Path, heading: str, detail: str) -> None:
    image = Image.open(source).convert("RGB")
    if image.width < 500 or image.height < 300:
        raise ValueError(f"runtime frame too small: {source}")
    canvas = Image.new("RGB", (1920, 1080), "#0d1b24")
    image.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
    scale = min(1920 / image.width, 1080 / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    canvas.paste(image, ((1920 - image.width) // 2, (1080 - image.height) // 2))
    layer = Image.new("RGBA", canvas.size)
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((72, 56, 785, 220), radius=22, fill=(9, 28, 38, 222))
    draw.rounded_rectangle((72, 934, 1290, 1020), radius=18, fill=(9, 28, 38, 222))
    draw.text((102, 75), heading, font=ImageFont.truetype(FONT, 52), fill="#eaffef")
    draw.text((102, 153), detail, font=ImageFont.truetype(FONT, 28), fill="#a7e5b5")
    draw.text((102, 955), "Демо-сцена · не обмер реального объекта · без подтверждения допуска",
              font=ImageFont.truetype(FONT, 24), fill="#e8f3ec")
    canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
    canvas.save(target, optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    public_frames = OUTPUT / "frames"
    public_frames.mkdir(parents=True, exist_ok=True)
    inputs = []
    manifest = []
    for index, (kind, view, heading, detail) in enumerate(SECTIONS):
        source = FRAMES / f"{kind}-{view}.png"
        if not source.is_file():
            raise FileNotFoundError(f"capture the real runtime first: {source}")
        frame = FRAMES / f"chapter-{index + 1}.png"
        prepared_frame(source, frame, heading, detail)
        Image.open(frame).resize((960, 540), Image.Resampling.LANCZOS).save(
            public_frames / f"chapter-{index + 1}.jpg", quality=84, optimize=True)
        inputs.extend(["-i", str(frame)])
        manifest.append({"chapter": index + 1, "kind": kind, "view": view,
                         "start_s": index * 30, "duration_s": 30,
                         "runtime_capture": str(source.relative_to(ROOT)).replace("\\", "/"),
                         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    filters = []
    for index in range(len(SECTIONS)):
        filters.append(f"[{index}:v]zoompan=z='min(zoom+0.00015,1.07)':d=720:"
                       "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                       f"s=1920x1080:fps=24,setsar=1[v{index}]")
    filters.append("".join(f"[v{i}]" for i in range(len(SECTIONS))) + "concat=n=6:v=1:a=0[out]")
    master = OUTPUT / "robodovod-trailer-master-1080p.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
        "-filter_complex", ";".join(filters), "-map", "[out]", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", str(master)], check=True)
    web = OUTPUT / "robodovod-trailer-web-720p.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(master),
        "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(web)], check=True)
    preview = OUTPUT / "robodovod-trailer-preview-720p.mp4"
    picks = "+".join(f"between(t,{index * 30},{index * 30 + 2})" for index in range(6))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(web),
        "-vf", f"select='{picks}',setpts=N/(24*TB)", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-an", str(preview)], check=True)
    Image.open(FRAMES / "chapter-1.png").resize((1280, 720), Image.Resampling.LANCZOS).save(
        OUTPUT / "robodovod-trailer-poster.jpg", quality=85, optimize=True)
    vtt = ["WEBVTT", ""]
    for index, (_, _, heading, detail) in enumerate(SECTIONS):
        start, end = index * 30, (index + 1) * 30
        vtt.extend([f"{start // 60:02d}:{start % 60:02d}.000 --> {end // 60:02d}:{end % 60:02d}.000",
                    f"{heading}. {detail}. Демонстрационная сцена; реальные условия требуют проверки.", ""])
    (OUTPUT / "robodovod-trailer.ru.vtt").write_text("\n".join(vtt), encoding="utf-8")
    (OUTPUT / "manifest.json").write_text(json.dumps({"status": "RUNTIME_CAPTURE_EDIT",
        "audio": "NONE_SILENT", "duration_s": 180, "master": master.name,
        "web": web.name, "preview": preview.name, "sections": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {master} ({master.stat().st_size} bytes), {web} ({web.stat().st_size} bytes), "
          f"{preview} ({preview.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
