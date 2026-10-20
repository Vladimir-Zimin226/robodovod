"""Validate the locally built, six-chapter runtime-capture trailer."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "frontend/public/demo/trailer"


def probe(path: Path) -> dict:
    output = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_name,codec_type,width,height,r_frame_rate:format=duration",
        "-of", "json", str(path)])
    return json.loads(output)


def frame(path: Path, second: int) -> bytes:
    return subprocess.check_output(["ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(second), "-i", str(path), "-frames:v", "1", "-f", "image2pipe",
        "-vcodec", "png", "-"])


def main() -> None:
    manifest = json.loads((VIDEO / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "RUNTIME_CAPTURE_EDIT" and manifest["audio"] == "NONE_SILENT"
    assert len(manifest["sections"]) == 6
    assert [(row["kind"], row["view"], row["start_s"]) for row in manifest["sections"]] == [
        ("warehouse", "3d", 0), ("warehouse", "2d", 30),
        ("airport", "3d", 60), ("airport", "2d", 90),
        ("clinic", "3d", 120), ("clinic", "2d", 150)]
    for row in manifest["sections"]:
        source = ROOT / row["runtime_capture"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"]
    specs = [("robodovod-trailer-master-1080p.mp4", (1920, 1080), 180),
             ("robodovod-trailer-web-720p.mp4", (1280, 720), 180),
             ("robodovod-trailer-preview-720p.mp4", (1280, 720), 12.25)]
    for filename, size, seconds in specs:
        metadata = probe(VIDEO / filename)
        video = [stream for stream in metadata["streams"] if stream["codec_type"] == "video"]
        assert len(video) == 1 and video[0]["codec_name"] == "h264"
        assert (video[0]["width"], video[0]["height"]) == size
        assert not any(stream["codec_type"] == "audio" for stream in metadata["streams"])
        assert abs(float(metadata["format"]["duration"]) - seconds) < 0.1
    master = VIDEO / "robodovod-trailer-master-1080p.mp4"
    signatures = []
    for second in (15, 45, 75, 105, 135, 165):
        image = Image.open(io.BytesIO(frame(master, second)))
        assert image.size == (1920, 1080)
        assert max(ImageStat.Stat(image.resize((128, 72))).stddev) > 15
        signatures.append(hashlib.sha256(image.tobytes()).hexdigest())
    assert len(set(signatures)) == 6
    captions = (VIDEO / "robodovod-trailer.ru.vtt").read_text(encoding="utf-8")
    assert captions.startswith("WEBVTT") and captions.count("-->") == 6
    assert all((VIDEO / "frames" / f"chapter-{number}.jpg").is_file() for number in range(1, 7))
    print("PASS trailer: six runtime chapters, H.264 1080p/720p, 180 s, teaser, captions, silent")


if __name__ == "__main__":
    main()
