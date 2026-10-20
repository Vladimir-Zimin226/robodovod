"""Add the customer supplied music to the existing 60 second trailer without re-encoding video.

The source WAV stays in Разобрать, outside the web asset directory. Rerun the
motion-trailer build before this script when the video frames change.
"""

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Разобрать/Dead morose WMD 2.wav"
TRAILER = ROOT / "frontend/public/demo/trailer"
VIDEO_NAMES = ("robodovod-trailer-web-720p.mp4", "robodovod-trailer-master-1080p.mp4")


def mux(path: Path) -> None:
    temporary = path.with_name(path.stem + ".music.tmp.mp4")
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(path), "-i", str(SOURCE),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-af", "atrim=duration=60,asetpts=PTS-STARTPTS,volume=0.88,"
                   "afade=t=in:st=0:d=0.5,afade=t=out:st=57.2:d=2.8",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-t", "60", "-movflags", "+faststart", str(temporary),
        ], check=True)
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_name,codec_type", "-of", "json", str(temporary),
        ]))
        codecs = {item["codec_type"]: item["codec_name"] for item in probe["streams"]}
        if codecs.get("video") != "h264" or codecs.get("audio") != "aac" \
                or abs(float(probe["format"]["duration"]) - 60) > 0.1:
            raise ValueError(f"unexpected trailer streams: {probe}")
        temporary.replace(path)
        print(f"{path.name}: h264 + aac, {probe['format']['duration']} s")
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    for name in VIDEO_NAMES:
        mux(TRAILER / name)
    manifest_path = TRAILER / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["audio"] = "CUSTOMER_SUPPLIED_WAV_AAC_IN_FULL_TRAILER; SILENT_PREVIEW"
    manifest["music_source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    manifest["music_source_duration_s"] = 121
    manifest["music_used_duration_s"] = 60
    for name in VIDEO_NAMES:
        manifest["sha256"][name] = hashlib.sha256((TRAILER / name).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
