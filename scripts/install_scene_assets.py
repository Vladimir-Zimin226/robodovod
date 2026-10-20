"""Verify and install the bundled original GLB meshes for the web scene."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Разобрать/ROBODOVOD_CODEX_SOL6_EXECUTION_PACKAGE_2026-10-20/ROBODOVOD_CODEX_PACKAGE"
DEST = ROOT / "frontend/public/scene-assets"


def main() -> None:
    source_manifest = json.loads((PACKAGE / "03_ASSETS_READY/ASSETS_MANIFEST.json").read_text(encoding="utf-8"))
    assets = source_manifest["original_meshes"]
    if len(assets) != 21 or len({asset["asset_id"] for asset in assets}) != 21:
        raise ValueError("expected 21 distinct bundled meshes")
    DEST.mkdir(parents=True, exist_ok=True)
    installed = []
    for asset in assets:
        source = PACKAGE / asset["path"]
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != asset["bytes"] or digest != asset["sha256"]:
            raise ValueError(f"bundled mesh failed integrity check: {asset['asset_id']}")
        target = DEST / f"{asset['asset_id']}.glb"
        shutil.copyfile(source, target)
        installed.append({"asset_id": asset["asset_id"], "file": target.name,
                          "sha256": digest, "bytes": len(data), "quality": asset["quality"]})
    (DEST / "manifest.json").write_text(json.dumps({"version": 1,
        "license": "Original procedural geometry; generated for this project",
        "assets": installed}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Installed and verified {len(installed)} GLB meshes")


if __name__ == "__main__":
    main()
