"""The generated SceneModel files must still represent the supplied fixtures."""

import json
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/scene-fixtures"
MODELS = ROOT / "data/scenes"


@pytest.mark.parametrize("kind", ["warehouse", "airport", "clinic"])
def test_shared_scene_matches_supplied_fixture(kind):
    fixture = json.loads((FIXTURES / f"{kind}.scene.json").read_text(encoding="utf-8"))
    scene = json.loads((MODELS / f"{kind}.scene.json").read_text(encoding="utf-8"))
    assert scene["schema_version"] == "scene-model-v1"
    assert scene["units"] == "m" and scene["coordinate_system"] == fixture["coordinate_system"]
    assert scene["fidelity"] == "DEMO_ASSUMPTION"
    obstacle_objects = [obj for obj in scene["objects"] if obj["blocks_navigation"]]
    visual_objects = [obj for obj in scene["objects"] if obj.get("visual_only")]
    assert len(obstacle_objects) == len(fixture["obstacles"])
    assert visual_objects and all(not obj["blocks_navigation"] for obj in visual_objects)
    assert len(scene["zones"]) == len(fixture["zones"])
    for obstacle, obj in zip(fixture["obstacles"], obstacle_objects):
        assert obj["position_m"][:2] == [obstacle["x"], obstacle["y"]]
        assert obj["footprint_m"] == [obstacle["width"], obstacle["height"]]
        assert obj["source"] == "DEMO_ASSUMPTION"
    for zone, converted in zip(fixture["zones"], scene["zones"]):
        assert converted["center_xy_m"] == [zone["x"], zone["y"]]
        assert converted["radius_m"] == zone["r"]
    assert [route["points_xy_m"] for route in scene["routes"]] == fixture["routes"]
    assert scene["nav"]["status"] == "NOT_EVALUATED"


def test_all_bundled_glb_assets_are_installed_and_referenced():
    asset_root = ROOT / "frontend/public/scene-assets"
    manifest = json.loads((asset_root / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["assets"]) == len({item["asset_id"] for item in manifest["assets"]}) == 21
    scene_ids = set()
    for kind in ("warehouse", "airport", "clinic"):
        scene = json.loads((MODELS / f"{kind}.scene.json").read_text(encoding="utf-8"))
        scene_ids.update(obj["asset_id"] for obj in scene["objects"])
    assert scene_ids == {item["asset_id"] for item in manifest["assets"]}
    for item in manifest["assets"]:
        data = (asset_root / item["file"]).read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
