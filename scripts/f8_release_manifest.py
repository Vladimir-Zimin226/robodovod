"""Create checksums for the local delivery artifacts (no signing or publish)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / "docs" / "delivery" / "f8"
files = {}
for path in sorted(directory.iterdir()):
    if path.is_file() and path.name != "manifest.json":
        data = path.read_bytes()
        files[path.name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
(directory / "manifest.json").write_text(json.dumps({"status": "LOCAL_CANDIDATE_NOT_PRODUCTION_ACCEPTED",
    "files": files}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(directory / "manifest.json")
