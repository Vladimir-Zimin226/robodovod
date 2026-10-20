"""Convert the supplied demo fixtures into the shared, versioned scene contract."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/scene-fixtures"
TARGET = ROOT / "data/scenes"

# Heights are visual template assumptions: the 2D fixtures contain footprints only.
VISUAL_HEIGHT_M = {
    "pallet_rack": 5.0,
    "conveyor": 1.0,
    "baggage_cart": 1.2,
    "aircraft_marker": 2.05,
    "hospital_bed": 1.7,
    "nurse_desk": 1.1,
}
ZONE_KIND = {"charging": "CHARGE", "pickup": "PICKUP", "delivery": "DROPOFF"}

# Visual template props reuse the bundled meshes. They do not add unverified
# obstacles to the route planner; their placement is explicitly an assumption.
VISUAL_PROPS = {
    "warehouse": [
        ("pallet_stack", 54, 6, 1.8, 1.2, 1.2),
        ("pallet_amr", 6, 34, 1.9, 1.3, .55),
        ("forklift_robot", 52, 8, 2.2, 1.3, 2.4),
        ("charging_dock", 5, 5, 1.8, 1.2, 1.5),
        ("worker", 5, 26, .7, .5, 1.8),
        ("warehouse_column", 57, 20, .5, .5, 4),
        ("door_frame", 56, 38, 2, .2, 2.5),
        ("painted_floor_marker", 30, 36, 3, .12, .02),
    ],
    "airport": [
        ("airport_tug", 43, 39, 2.3, 1.2, 1.5),
        ("safety_barrier", 37, 42, 2.3, .2, 1.1),
        ("traffic_cone", 33, 41, .5, .5, .8),
        ("worker", 27, 38, .7, .5, 1.8),
        ("painted_floor_marker", 50, 43, 3, .12, .02),
    ],
    "clinic": [
        ("hospital_cart", 39, 5, .9, .7, 1.4),
        ("indoor_delivery_robot", 4, 14, .7, .7, 1.2),
        ("clinic_wall_module", 41, 23, 3, .2, 2.5),
        ("clinic_door", 41, 19, 1, .2, 2.3),
        ("worker", 37, 23, .7, .5, 1.8),
    ],
}


def build_scene(fixture: dict) -> dict:
    if (fixture["schema_version"], fixture["units"], fixture["coordinate_system"]) != (
        "scene-fixture-1", "meters", "x-east_y-north_z-up"
    ):
        raise ValueError("unsupported fixture coordinate contract")
    width, length = fixture["size_m"]
    if min(width, length) <= 0:
        raise ValueError("scene bounds must be positive")
    objects = []
    for index, item in enumerate(fixture["obstacles"], 1):
        x, y, dx, dy = (float(item[key]) for key in ("x", "y", "width", "height"))
        if min(dx, dy) <= 0 or x - dx / 2 < 0 or x + dx / 2 > width or y - dy / 2 < 0 or y + dy / 2 > length:
            raise ValueError(f"obstacle {index} falls outside scene bounds")
        objects.append({
            "instance_id": f"{item['asset_id']}-{index:03d}", "asset_id": item["asset_id"],
            "position_m": [x, y, 0], "rotation_yaw_rad": 0,
            "scale": [1, 1, 1], "footprint_m": [dx, dy],
            "visual_height_m": VISUAL_HEIGHT_M[item["asset_id"]],
            "blocks_navigation": True, "source": "DEMO_ASSUMPTION",
        })
    for index, (asset_id, x, y, dx, dy, height) in enumerate(VISUAL_PROPS[fixture["scene_id"]], 1):
        if x - dx / 2 < 0 or x + dx / 2 > width or y - dy / 2 < 0 or y + dy / 2 > length:
            raise ValueError(f"visual prop {asset_id} outside scene bounds")
        objects.append({
            "instance_id": f"visual-{asset_id}-{index:03d}", "asset_id": asset_id,
            "position_m": [x, y, 0], "rotation_yaw_rad": 0, "scale": [1, 1, 1],
            "footprint_m": [dx, dy], "visual_height_m": height,
            "blocks_navigation": False, "visual_only": True, "source": "DEMO_ASSUMPTION",
        })
    zones = []
    for item in fixture["zones"]:
        x, y, radius = (float(item[key]) for key in ("x", "y", "r"))
        if radius <= 0 or x - radius < 0 or x + radius > width or y - radius < 0 or y + radius > length:
            raise ValueError(f"zone {item['id']} falls outside scene bounds")
        polygon = [[round(x + radius * math.cos(2 * math.pi * i / 24), 6),
                    round(y + radius * math.sin(2 * math.pi * i / 24), 6)] for i in range(24)]
        zones.append({"zone_id": item["id"], "name": item["name"],
                      "kind": ZONE_KIND[item["id"]], "center_xy_m": [x, y],
                      "radius_m": radius, "polygon_xy_m": polygon,
                      "capacity": 1, "source": "DEMO_ASSUMPTION"})
    routes = []
    for index, route in enumerate(fixture["routes"], 1):
        points = [[float(x), float(y)] for x, y in route]
        if len(points) < 2 or any(x < 0 or x > width or y < 0 or y > length for x, y in points):
            raise ValueError(f"route {index} falls outside scene bounds")
        routes.append({"route_id": f"demo-{index}", "points_xy_m": points,
                       "source": "DEMO_ASSUMPTION", "status": "UNVALIDATED_GEOMETRY"})
    return {
        "schema_version": "scene-model-v1", "scene_id": fixture["scene_id"],
        "revision": 1, "units": "m", "coordinate_system": "x-east_y-north_z-up",
        "bounds": {"width_m": width, "length_m": length, "height_m": 9},
        "fidelity": "DEMO_ASSUMPTION", "source_fixture": f"{fixture['scene_id']}.scene.json",
        "objects": objects, "zones": zones, "routes": routes,
        "agents": [], "tasks": [],
        "nav": {"no_go_polygons_xy_m": [], "one_way_edges": [], "min_clearance_m": None,
                "status": "NOT_EVALUATED"},
        "links": {"catalog_version": None, "assessment_revision": None},
    }


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for kind in ("warehouse", "airport", "clinic"):
        fixture = json.loads((SOURCE / f"{kind}.scene.json").read_text(encoding="utf-8"))
        scene = build_scene(fixture)
        (TARGET / f"{kind}.scene.json").write_text(
            json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{kind}: {len(scene['objects'])} objects, {len(scene['zones'])} zones, {len(scene['routes'])} routes")


if __name__ == "__main__":
    main()
