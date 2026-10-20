"""Acceptance checks for path, events, deterministic fleet and honest unknowns."""

import pytest

from calculation.scene_simulation import ExtraObstacle, SceneSimulationInput, SharedLane, load_scene, simulate_scene


def configured(**changes):
    return SceneSimulationInput(**{
        "scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
        "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
        "units_per_cycle": 1, "demand_units_per_hour": 35,
        "robot_availability": 0.75, **changes,
    })


def test_obstacle_reroutes_and_changes_required_fleet():
    scene = load_scene("warehouse")
    baseline = simulate_scene(scene, configured())
    blocked_line = simulate_scene(scene, configured(extra_obstacles=[
        ExtraObstacle(x=25, y=34, width=2, height=2)]))
    assert baseline["status"] == blocked_line["status"] == "MODELED"
    assert baseline["distance_loaded_m"] < blocked_line["distance_loaded_m"]
    assert baseline["cycle_s"] < blocked_line["cycle_s"]
    assert baseline["fleet_required"] == 2
    assert blocked_line["fleet_required"] == 3
    assert simulate_scene(scene, configured()) == baseline


def test_moving_pickup_changes_authoritative_route_and_rejects_invalid_zone():
    scene = load_scene("warehouse")
    original = simulate_scene(scene, configured())
    moved = simulate_scene(scene, configured(pickup_xy_m=(11, 31)))
    assert moved["routes"][0]["points_xy_m"][0] == [11, 31]
    assert moved["distance_loaded_m"] != original["distance_loaded_m"]
    with pytest.raises(ValueError, match="moved zone"):
        simulate_scene(scene, configured(pickup_xy_m=(0, 0)))


def test_wall_across_floor_stops_robot_without_fictitious_throughput():
    result = simulate_scene(load_scene("warehouse"), configured(extra_obstacles=[
        ExtraObstacle(x=30, y=20, width=1, height=40)]))
    assert result["status"] == "NO_ROUTE"
    assert result["fleet_required"] is None
    assert result["throughput_per_hour"] is None
    assert "NO_ROUTE" in result["flags"]


def test_missing_speed_is_needs_input_and_event_queue_can_block_capacity():
    scene = load_scene("warehouse")
    missing = simulate_scene(scene, SceneSimulationInput(scene_revision=1))
    assert missing["status"] == "NEEDS_INPUT"
    assert "speed_loaded_mps" in missing["missing"]
    assert missing["fleet_required"] is None
    overloaded = simulate_scene(scene, configured(demand_units_per_hour=100, pickup_service_s=40))
    assert overloaded["status"] == "CAPACITY_SHORTFALL"
    assert overloaded["time_wait_s"] > 0
    assert "PICKUP_QUEUE" in overloaded["bottlenecks"]
    assert overloaded["fleet_required"] is None


def test_explicit_burst_creates_stable_queue_and_increases_fleet():
    scene = load_scene("warehouse")
    uniform = simulate_scene(scene, configured())
    burst = simulate_scene(scene, configured(arrival_burst_size=4))
    assert uniform["status"] == burst["status"] == "MODELED"
    assert uniform["time_wait_s"] == 0
    assert burst["time_wait_s"] > 0
    assert "BURST_QUEUE" in burst["bottlenecks"]
    assert uniform["fleet_required"] < burst["fleet_required"]


def test_shared_lane_serializes_opposing_flow_and_changes_fleet():
    scene = load_scene("warehouse")
    baseline = simulate_scene(scene, configured())
    value = configured(shared_lane=SharedLane(x=30, y=34, width=30, height=2))
    queued = simulate_scene(scene, value)
    assert queued["status"] == "MODELED"
    assert queued == simulate_scene(scene, value)
    assert queued["shared_lane"]["mean_wait_s"] > 0
    assert queued["time_wait_s"] > baseline["time_wait_s"]
    assert queued["fleet_required"] > baseline["fleet_required"]
    assert "SHARED_LANE_QUEUE" in queued["bottlenecks"]
    assert "SHARED_EDGE_QUEUE_NOT_MODELED" not in queued["flags"]
    assert "OTHER_SHARED_EDGES_NOT_MODELED" in queued["flags"]
    intervals = queued["shared_lane"]["event_sample"]
    assert len(intervals) == 200 and queued["shared_lane"]["events"] == 280
    assert all(left["end_s"] <= right["start_s"] + 0.001
               for left, right in zip(intervals, intervals[1:]))
    overloaded = simulate_scene(scene, configured(demand_units_per_hour=80,
        shared_lane=SharedLane(x=30, y=34, width=30, height=2)))
    assert overloaded["status"] == "CAPACITY_SHORTFALL"
    assert "SHARED_LANE_OVERLOAD" in overloaded["bottlenecks"]
    assert overloaded["fleet_required"] is None


def test_shared_lane_requires_contiguous_crossing_on_both_routes():
    scene = load_scene("warehouse")
    with pytest.raises(ValueError, match="outside"):
        simulate_scene(scene, configured(shared_lane=SharedLane(x=0, y=34, width=4, height=2)))
    with pytest.raises(ValueError, match="does not cross"):
        simulate_scene(scene, configured(shared_lane=SharedLane(x=30, y=10, width=4, height=2)))


@pytest.mark.parametrize("kind", ["warehouse", "airport", "clinic"])
def test_three_demo_scenes_have_a_deterministic_path(kind):
    scene = load_scene(kind)
    result = simulate_scene(scene, configured(demand_units_per_hour=10))
    assert result["status"] == "MODELED"
    assert result["scene_revision"] == scene["revision"]
    assert len(result["routes"]) == 2
    assert result["timestep_pose_samples"]


def test_stale_scene_revision_and_invalid_patch_are_rejected():
    scene = load_scene("warehouse")
    with pytest.raises(ValueError, match="revision"):
        simulate_scene(scene, configured(scene_revision=2))
    with pytest.raises(ValueError, match="outside"):
        simulate_scene(scene, configured(extra_obstacles=[ExtraObstacle(x=0, y=0, width=5, height=5)]))
