"""Deterministic preliminary transport simulation over the shared SceneModel."""

from __future__ import annotations

import heapq
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCENES = Path(__file__).resolve().parents[2] / "data/scenes"
CELL_M = 0.5
HORIZON_H = 4
MAX_JOBS = 10000
MAX_FLEET = 100


class ExtraObstacle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SharedLane(BaseModel):
    """User-defined single-occupancy rectangle crossed in both directions."""

    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SceneSimulationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_revision: int = Field(ge=1)
    pickup_xy_m: tuple[float, float] | None = None
    dropoff_xy_m: tuple[float, float] | None = None
    extra_obstacles: list[ExtraObstacle] = Field(default_factory=list, max_length=50)
    shared_lane: SharedLane | None = None
    clearance_m: float = Field(default=0.3, ge=0, le=2)
    speed_loaded_mps: float | None = Field(default=None, gt=0, le=10)
    speed_empty_mps: float | None = Field(default=None, gt=0, le=10)
    pickup_service_s: float | None = Field(default=None, ge=0, le=3600)
    dropoff_service_s: float | None = Field(default=None, ge=0, le=3600)
    turn_delay_s: float | None = Field(default=None, ge=0, le=3600)
    units_per_cycle: float | None = Field(default=None, gt=0, le=1000)
    demand_units_per_hour: float | None = Field(default=None, gt=0, le=100000)
    robot_availability: float | None = Field(default=None, gt=0, le=1)
    fleet_reserve_share: float = Field(default=0, ge=0, le=1)
    arrival_burst_size: int = Field(default=1, ge=1, le=20)
    selected_robot_ids: list[str] = Field(default_factory=list, max_length=100)


@lru_cache(maxsize=3)
def load_scene(kind: str) -> dict[str, Any]:
    if kind not in {"warehouse", "airport", "clinic"}:
        raise ValueError("unknown demo scene")
    scene = json.loads((SCENES / f"{kind}.scene.json").read_text(encoding="utf-8"))
    if scene["schema_version"] != "scene-model-v1" or scene["units"] != "m":
        raise ValueError("unsupported SceneModel")
    return scene


def _inside(point: tuple[float, float], scene: dict) -> bool:
    x, y = point
    return (math.isfinite(x) and math.isfinite(y) and 0 <= x <= scene["bounds"]["width_m"]
            and 0 <= y <= scene["bounds"]["length_m"])


def _blocked(point: tuple[float, float], objects: list[dict], clearance: float) -> bool:
    x, y = point
    for obj in objects:
        ox, oy = obj["position_m"][:2]
        dx, dy = obj["footprint_m"]
        if abs(x - ox) <= dx / 2 + clearance and abs(y - oy) <= dy / 2 + clearance:
            return True
    return False


def _route(scene: dict, start: tuple[float, float], end: tuple[float, float],
           objects: list[dict], clearance: float) -> list[list[float]] | None:
    if not _inside(start, scene) or not _inside(end, scene):
        raise ValueError("route endpoint outside scene bounds")
    width = round(scene["bounds"]["width_m"] / CELL_M)
    length = round(scene["bounds"]["length_m"] / CELL_M)
    first = (round(start[0] / CELL_M), round(start[1] / CELL_M))
    last = (round(end[0] / CELL_M), round(end[1] / CELL_M))
    blocked = set()
    # Inflate by half a cell: an occupied cell cannot clip an obstacle corner.
    for ix in range(width + 1):
        for iy in range(length + 1):
            if _blocked((ix * CELL_M, iy * CELL_M), objects, clearance + CELL_M / 2):
                blocked.add((ix, iy))
    if first in blocked or last in blocked or _blocked(start, objects, clearance) or _blocked(end, objects, clearance):
        return None
    frontier = [(abs(first[0] - last[0]) + abs(first[1] - last[1]), 0, first)]
    distance = {first: 0}
    previous = {}
    while frontier:
        _, cost, node = heapq.heappop(frontier)
        if cost != distance[node]:
            continue
        if node == last:
            path = [node]
            while path[-1] != first:
                path.append(previous[path[-1]])
            path.reverse()
            # Keep turns and endpoints. This is the same route used by all views.
            compressed = [path[0]]
            for index in range(1, len(path) - 1):
                a, b, c = path[index - 1:index + 2]
                if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                    compressed.append(b)
            if path[-1] != compressed[-1]:
                compressed.append(path[-1])
            points = [[start[0], start[1]]]
            points.extend([[x * CELL_M, y * CELL_M] for x, y in compressed])
            points.append([end[0], end[1]])
            return [point for index, point in enumerate(points) if index == 0 or point != points[index - 1]]
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            neighbor = (node[0] + dx, node[1] + dy)
            if not (0 <= neighbor[0] <= width and 0 <= neighbor[1] <= length) or neighbor in blocked:
                continue
            new_cost = cost + 1
            if new_cost < distance.get(neighbor, math.inf):
                distance[neighbor] = new_cost
                previous[neighbor] = node
                heuristic = abs(neighbor[0] - last[0]) + abs(neighbor[1] - last[1])
                heapq.heappush(frontier, (new_cost + heuristic, new_cost, neighbor))
    return None


def _length(points: list[list[float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _queue(requests_per_hour: float, pickup_s: float, dropoff_s: float,
           loaded_s: float, horizon_h: int, burst_size: int) -> tuple[float, float, bool, int]:
    jobs = max(1, math.ceil(requests_per_hour * horizon_h))
    if jobs > MAX_JOBS:
        raise ValueError("demand exceeds simulation event limit")
    pickup_free = dropoff_free = total_wait = max_wait = 0.0
    for index in range(jobs):
        arrival = (index // burst_size) * burst_size * 3600 / requests_per_hour
        pickup_start = max(arrival, pickup_free)
        pickup_wait = pickup_start - arrival
        pickup_free = pickup_start + pickup_s
        dropoff_arrival = pickup_free + loaded_s
        dropoff_start = max(dropoff_arrival, dropoff_free)
        dropoff_wait = dropoff_start - dropoff_arrival
        dropoff_free = dropoff_start + dropoff_s
        wait = pickup_wait + dropoff_wait
        total_wait += wait
        max_wait = max(max_wait, wait)
    unstable = pickup_free > horizon_h * 3600 + pickup_s or dropoff_free > horizon_h * 3600 + loaded_s + dropoff_s
    return total_wait / jobs, max_wait, unstable, jobs


def _lane_sections(route: list[list[float]], lane: SharedLane) -> tuple[float, float, float]:
    """Distance before, inside, and after a contiguous rectangular lane crossing."""
    limits = ((lane.x - lane.width / 2, lane.x + lane.width / 2),
              (lane.y - lane.height / 2, lane.y + lane.height / 2))
    intervals = []
    distance = 0.0
    for a, b in zip(route, route[1:]):
        segment = math.dist(a, b)
        if not segment:
            continue
        enter, leave = 0.0, 1.0
        for axis in range(2):
            delta = b[axis] - a[axis]
            low, high = limits[axis]
            if abs(delta) < 1e-12:
                if a[axis] < low or a[axis] > high:
                    leave = -1
                    break
            else:
                first, last = sorted(((low - a[axis]) / delta, (high - a[axis]) / delta))
                enter, leave = max(enter, first), min(leave, last)
        if leave - enter > 1e-9:
            intervals.append((distance + enter * segment, distance + leave * segment))
        distance += segment
    if not intervals:
        raise ValueError("shared lane does not cross both routes")
    first, last = intervals[0]
    for start, end in intervals[1:]:
        if start > last + 1e-6:
            raise ValueError("shared lane crosses a route more than once")
        last = max(last, end)
    return first, last - first, distance - last


def _queue_with_lane(requests_per_hour: float, pickup_s: float, dropoff_s: float,
                     loaded_sections: tuple[float, float, float],
                     empty_sections: tuple[float, float, float],
                     loaded_speed: float, empty_speed: float,
                     horizon_h: int, burst_size: int) -> dict[str, Any]:
    """Chronological pickup, lane and dropoff events; lane capacity is one robot."""
    jobs = max(1, math.ceil(requests_per_hour * horizon_h))
    if jobs > MAX_JOBS:
        raise ValueError("demand exceeds simulation event limit")
    events: list[tuple[float, int, str, int]] = []
    sequence = 0

    def schedule(when: float, stage: str, job: int) -> None:
        nonlocal sequence
        heapq.heappush(events, (when, sequence, stage, job))
        sequence += 1

    for index in range(jobs):
        schedule((index // burst_size) * burst_size * 3600 / requests_per_hour, "pickup", index)
    pickup_free = dropoff_free = lane_free = 0.0
    station_wait = [0.0] * jobs
    lane_wait = [0.0] * jobs
    intervals = []
    while events:
        when, _, stage, job = heapq.heappop(events)
        if stage == "pickup":
            begin = max(when, pickup_free)
            station_wait[job] += begin - when
            pickup_free = begin + pickup_s
            schedule(pickup_free + loaded_sections[0] / loaded_speed, "loaded_lane", job)
        elif stage == "loaded_lane" or stage == "empty_lane":
            begin = max(when, lane_free)
            lane_wait[job] += begin - when
            section = loaded_sections if stage == "loaded_lane" else empty_sections
            speed = loaded_speed if stage == "loaded_lane" else empty_speed
            lane_free = begin + section[1] / speed
            intervals.append({"job": job, "direction": "LOADED" if stage == "loaded_lane" else "EMPTY",
                              "start_s": round(begin, 3), "end_s": round(lane_free, 3)})
            if stage == "loaded_lane":
                schedule(lane_free + section[2] / speed, "dropoff", job)
        elif stage == "dropoff":
            begin = max(when, dropoff_free)
            station_wait[job] += begin - when
            dropoff_free = begin + dropoff_s
            schedule(dropoff_free + empty_sections[0] / empty_speed, "empty_lane", job)
    lane_service_s = loaded_sections[1] / loaded_speed + empty_sections[1] / empty_speed
    capacity = min(3600 / pickup_s if pickup_s else math.inf,
                   3600 / dropoff_s if dropoff_s else math.inf, 3600 / lane_service_s)
    waits = [station + lane for station, lane in zip(station_wait, lane_wait)]
    return {"mean_wait_s": sum(waits) / jobs, "max_wait_s": max(waits), "jobs": jobs,
            "unstable": requests_per_hour >= capacity - 1e-9,
            "mean_lane_wait_s": sum(lane_wait) / jobs, "max_lane_wait_s": max(lane_wait),
            "lane_capacity_per_hour": 3600 / lane_service_s,
            "lane_events": len(intervals), "lane_event_sample": intervals[:200]}


def simulate_scene(scene: dict, value: SceneSimulationInput) -> dict[str, Any]:
    if value.scene_revision != scene["revision"]:
        raise ValueError("scene revision changed; reload before simulation")
    zones = {zone["zone_id"]: zone for zone in scene["zones"]}
    start = value.pickup_xy_m or tuple(zones["pickup"]["center_xy_m"])
    end = value.dropoff_xy_m or tuple(zones["delivery"]["center_xy_m"])
    for point, zone in ((start, zones["pickup"]), (end, zones["delivery"])):
        radius = zone["radius_m"]
        if (not _inside((point[0] - radius, point[1] - radius), scene)
                or not _inside((point[0] + radius, point[1] + radius), scene)):
            raise ValueError("moved zone falls outside scene bounds")
    extras = []
    for index, obstacle in enumerate(value.extra_obstacles, 1):
        if not _inside((obstacle.x - obstacle.width / 2, obstacle.y - obstacle.height / 2), scene) or not _inside(
            (obstacle.x + obstacle.width / 2, obstacle.y + obstacle.height / 2), scene):
            raise ValueError("extra obstacle outside scene bounds")
        extras.append({"instance_id": f"user-block-{index}", "position_m": [obstacle.x, obstacle.y, 0],
                       "footprint_m": [obstacle.width, obstacle.height], "blocks_navigation": True})
    objects = [obj for obj in scene["objects"] if obj["blocks_navigation"]] + extras
    if value.shared_lane:
        lane = value.shared_lane
        if not _inside((lane.x - lane.width / 2, lane.y - lane.height / 2), scene) or not _inside(
                (lane.x + lane.width / 2, lane.y + lane.height / 2), scene):
            raise ValueError("shared lane outside scene bounds")
    loaded = _route(scene, start, end, objects, value.clearance_m)
    empty = _route(scene, end, start, objects, value.clearance_m) if loaded is not None else None
    source = ["SceneModel demo geometry", "Grid A* 0.5 m; clearance is user/scenario input",
              f"Pickup and dropoff are single-server event resources; arrival burst size {value.arrival_burst_size}",
              "Battery/charging are not modeled"]
    source.append("User-defined single-occupancy shared lane" if value.shared_lane else
                  "Shared-edge traffic is not modeled without a lane scenario")
    base = {"schema_version": "scene-simulation-v1", "scene_id": scene["scene_id"],
            "scene_revision": scene["revision"], "selected_robot_ids": value.selected_robot_ids,
            "quality_status": "PRELIMINARY_DEMO_SCENARIO", "source_assumptions": source,
            "routes": [], "distance_loaded_m": None, "distance_empty_m": None,
            "time_travel_s": None, "time_wait_s": None, "time_service_s": None,
            "utilization": None, "throughput_per_hour": None, "fleet_required": None,
            "bottlenecks": [], "flags": (["SHARED_EDGE_QUEUE_NOT_MODELED"] if not value.shared_lane else
                                         ["OTHER_SHARED_EDGES_NOT_MODELED"])
            + ["CHARGING_NOT_MODELED", "SAFETY_NOT_VERIFIED"],
            "timestep_pose_samples": []}
    if loaded is None or empty is None:
        return {**base, "status": "NO_ROUTE", "flags": base["flags"] + ["NO_ROUTE"]}
    loaded_m, empty_m = _length(loaded), _length(empty)
    lane_sections = (_lane_sections(loaded, value.shared_lane), _lane_sections(empty, value.shared_lane)) \
        if value.shared_lane else None
    base.update(routes=[{"kind": "LOADED", "points_xy_m": loaded}, {"kind": "EMPTY", "points_xy_m": empty}],
                distance_loaded_m=round(loaded_m, 3), distance_empty_m=round(empty_m, 3))
    required = ("speed_loaded_mps", "speed_empty_mps", "pickup_service_s", "dropoff_service_s",
                "turn_delay_s", "units_per_cycle", "demand_units_per_hour", "robot_availability")
    missing = [key for key in required if getattr(value, key) is None]
    if missing:
        return {**base, "status": "NEEDS_INPUT", "flags": base["flags"] + ["NEEDS_INPUT"],
                "missing": missing}
    loaded_s = loaded_m / value.speed_loaded_mps
    empty_s = empty_m / value.speed_empty_mps
    requests_per_hour = value.demand_units_per_hour / value.units_per_cycle
    lane_stats = None
    if lane_sections:
        lane_stats = _queue_with_lane(requests_per_hour, value.pickup_service_s, value.dropoff_service_s,
                                      lane_sections[0], lane_sections[1], value.speed_loaded_mps,
                                      value.speed_empty_mps, HORIZON_H, value.arrival_burst_size)
        wait_s, max_wait_s, unstable, jobs = (lane_stats[key] for key in
                                              ("mean_wait_s", "max_wait_s", "unstable", "jobs"))
    else:
        wait_s, max_wait_s, unstable, jobs = _queue(requests_per_hour, value.pickup_service_s,
                                                    value.dropoff_service_s, loaded_s, HORIZON_H,
                                                    value.arrival_burst_size)
    service_s = value.pickup_service_s + value.dropoff_service_s + value.turn_delay_s
    cycle_s = loaded_s + empty_s + service_s + wait_s
    station_capacity = min(3600 / value.pickup_service_s if value.pickup_service_s else math.inf,
                           3600 / value.dropoff_service_s if value.dropoff_service_s else math.inf)
    if lane_stats:
        station_capacity = min(station_capacity, lane_stats["lane_capacity_per_hour"])
    bottlenecks = []
    if value.pickup_service_s and requests_per_hour >= 3600 / value.pickup_service_s:
        bottlenecks.append("PICKUP_QUEUE")
    if value.dropoff_service_s and requests_per_hour >= 3600 / value.dropoff_service_s:
        bottlenecks.append("DROPOFF_QUEUE")
    if lane_stats and lane_stats["mean_lane_wait_s"] > 1e-9:
        bottlenecks.append("SHARED_LANE_QUEUE")
    if lane_stats and requests_per_hour >= lane_stats["lane_capacity_per_hour"] - 1e-9:
        bottlenecks.append("SHARED_LANE_OVERLOAD")
    if wait_s > 0 and not bottlenecks:
        bottlenecks.append("BURST_QUEUE")
    target = value.demand_units_per_hour
    fleet = next((count for count in range(1, MAX_FLEET + 1)
                  if count * 3600 * value.robot_availability / cycle_s * value.units_per_cycle
                  >= target * (1 + value.fleet_reserve_share) - 1e-9), None)
    throughput = min((fleet or MAX_FLEET) * 3600 * value.robot_availability / cycle_s,
                     station_capacity) * value.units_per_cycle
    shortfall = unstable or fleet is None or throughput + 1e-9 < target
    flags = base["flags"] + (["QUEUE_UNSTABLE"] if unstable else [])
    if shortfall:
        flags.append("CAPACITY_SHORTFALL")
    # Sample poses follow the authoritative route; renderer interpolation is visual only.
    pose = []
    elapsed = 0.0
    for label, route, speed in (("LOADED", loaded, value.speed_loaded_mps),
                                 ("EMPTY", empty, value.speed_empty_mps)):
        for index, point in enumerate(route):
            if index:
                elapsed += math.dist(route[index - 1], point) / speed
            pose.append({"t_s": round(elapsed, 3), "x_m": point[0], "y_m": point[1], "stage": label})
    return {**base, "status": "CAPACITY_SHORTFALL" if shortfall else "MODELED",
            "time_travel_s": round(loaded_s + empty_s, 3), "time_wait_s": round(wait_s, 3),
            "time_service_s": round(service_s, 3), "cycle_s": round(cycle_s, 3),
            "max_wait_s": round(max_wait_s, 3), "simulated_jobs": jobs,
            "shared_lane": ({"geometry": value.shared_lane.model_dump(),
                             "mean_wait_s": round(lane_stats["mean_lane_wait_s"], 3),
                             "max_wait_s": round(lane_stats["max_lane_wait_s"], 3),
                             "capacity_per_hour": round(lane_stats["lane_capacity_per_hour"], 3),
                             "events": lane_stats["lane_events"],
                             "event_sample_truncated": lane_stats["lane_events"] > len(lane_stats["lane_event_sample"]),
                             "event_sample": lane_stats["lane_event_sample"]} if lane_stats else None),
            "utilization": round(requests_per_hour * cycle_s / (3600 * (fleet or MAX_FLEET)), 4),
            "throughput_per_hour": round(throughput, 3), "fleet_required": fleet if not shortfall else None,
            "bottlenecks": bottlenecks, "flags": flags, "timestep_pose_samples": pose}
