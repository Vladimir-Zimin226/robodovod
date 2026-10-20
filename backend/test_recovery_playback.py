"""The three authored scenes must produce usable server poses for UI playback."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.calculation.scene_simulation import SceneSimulationInput, load_scene, simulate_scene
from backend.calculation.warehouse_roles import warehouse_template
from backend.warehouse_roles_api import create_warehouse_roles_router


@pytest.mark.parametrize("kind", ["warehouse", "airport", "clinic"])
def test_demo_route_has_distinct_server_poses(kind):
    scene = load_scene(kind)
    scenario = SceneSimulationInput(
        scene_revision=scene["revision"], speed_loaded_mps=0.8, speed_empty_mps=1,
        pickup_service_s=25, dropoff_service_s=20, turn_delay_s=8,
        units_per_cycle=1, demand_units_per_hour=20, robot_availability=0.75,
    )
    result = simulate_scene(scene, scenario)
    poses = result["timestep_pose_samples"]
    assert result["status"] == "MODELED"
    assert len(poses) > 2
    assert poses[-1]["t_s"] > poses[1]["t_s"] > poses[0]["t_s"]
    assert len({(point["x_m"], point["y_m"]) for point in poses}) >= 2
    assert result["fleet_required"] is not None


@pytest.mark.parametrize("kind", ["warehouse", "airport", "clinic"])
def test_blocked_pickup_does_not_supply_moving_pose_or_confirmed_fleet(kind):
    scene = load_scene(kind)
    pickup = next(zone["center_xy_m"] for zone in scene["zones"] if zone["zone_id"] == "pickup")
    scenario = SceneSimulationInput(
        scene_revision=scene["revision"], speed_loaded_mps=0.8, speed_empty_mps=1,
        pickup_service_s=25, dropoff_service_s=20, turn_delay_s=8,
        units_per_cycle=1, demand_units_per_hour=20, robot_availability=0.75,
        extra_obstacles=[{"x": pickup[0], "y": pickup[1], "width": 3, "height": 3}],
    )
    result = simulate_scene(scene, scenario)
    assert result["status"] == "NO_ROUTE"
    assert result["timestep_pose_samples"] == []
    assert result["fleet_required"] is None


def test_guest_scenario_route_works_without_catalog_and_cannot_confirm_money():
    template = warehouse_template()
    role = next(row for row in template["roles"] if row["role_code"] == "forklift_driver")
    input_role = {key: role[key] for key in ("role_code", "headcount", "monthly_employer_cost_rub",
        "daily_volume", "manual_units_per_person_shift", "robotizable_share", "source", "basis")}
    input_role["simulation"] = {"scene_revision": load_scene("warehouse")["revision"],
        "speed_loaded_mps": .8, "speed_empty_mps": 1, "pickup_service_s": 25,
        "dropoff_service_s": 20, "turn_delay_s": 8, "units_per_cycle": 1}
    app = FastAPI()
    app.include_router(create_warehouse_roles_router(lambda: (_ for _ in ()).throw(AssertionError("catalog queried"))))
    client = TestClient(app)
    payload = {"input": {"general": template["general"], "roles": [input_role]}, "role_index": 0}
    response = client.post("/api/v2/warehouse-roles/route-preview", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["simulation"]["status"] == "MODELED"
    assert len(body["simulation"]["timestep_pose_samples"]) > 2
    assert body["simulation"]["selected_robot_ids"] == []
    assert "SCENARIO_ROBOT_ONLY" in body["simulation"]["flags"]
    assert body["catalog_robot_confirmed"] is False
    assert body["economics_confirmed"] is False
    assert "npv_rub" not in body
    payload["input"]["roles"][0]["simulation"]["extra_obstacles"] = [
        {"x": 11, "y": 34, "width": 3, "height": 3}]
    blocked = client.post("/api/v2/warehouse-roles/route-preview", json=payload)
    assert blocked.status_code == 200
    assert blocked.json()["simulation"]["status"] == "NO_ROUTE"
