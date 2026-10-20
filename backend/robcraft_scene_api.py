"""Versioned RobCraft scene documents owned by a saved project.

These visual documents are not inputs to a verified economics run.
"""

from __future__ import annotations

import json
import math
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from auth import AuthContext, require_auth_context, require_csrf
from database import database_session
from fastapi import APIRouter, Depends, HTTPException
from persistence_models import Project, Scenario
from persistence_api import SCENARIO_SLOTS
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

PROFILE_KEY = "robcraft_scene_v1"
MAX_DOCUMENT_BYTES = 350_000
MAX_VERSIONS = 8
AUTH = Depends(require_auth_context)
CSRF = Depends(require_csrf)
DB = Depends(database_session)


def _vector(value: Any, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)
        for item in value
    )


class SaveRobCraftScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=200)
    document: dict[str, Any]

    @model_validator(mode="after")
    def validate_document(self):
        document = self.document
        if set(document) - {"engine", "documentVersion", "base", "scenePatch", "inventory"}:
            raise ValueError("unknown RobCraft document fields")
        if document.get("engine") != "robcraft" or document.get("documentVersion") != 1:
            raise ValueError("unsupported RobCraft document")
        patch = document.get("scenePatch")
        base = document.get("base")
        if not isinstance(patch, dict) or patch.get("format") != "robcraft-scene-patch-v1" or not isinstance(base, dict):
            raise ValueError("invalid RobCraft ScenePatch")
        if patch.get("base") != base:
            raise ValueError("ScenePatch base differs from document base")
        required_patch_fields = {"format", "base", "objects", "created", "deleted", "robots"}
        if not required_patch_fields <= set(patch) or set(patch) - required_patch_fields - {"zones", "rooms", "assignments", "economics", "cad"}:
            raise ValueError("invalid ScenePatch fields")
        cad = patch.get("cad")
        if cad is not None:
            expected_cad = {"file_name", "unit_meters", "wall_height_m", "wall_layers", "obstacle_layers", "unsupported_entities", "malformed_entities"}
            if not isinstance(cad, dict) or set(cad) != expected_cad:
                raise ValueError("invalid CAD provenance fields")
            if not isinstance(cad["file_name"], str) or not 1 <= len(cad["file_name"]) <= 200 or not cad["file_name"].lower().endswith(".dxf") or "/" in cad["file_name"] or "\\" in cad["file_name"]:
                raise ValueError("invalid CAD file name")
            if any(not isinstance(cad[key], (int, float)) or isinstance(cad[key], bool) or not math.isfinite(cad[key]) or cad[key] <= 0 for key in ("unit_meters", "wall_height_m")):
                raise ValueError("invalid CAD scale")
            if any(not isinstance(cad[key], list) or len(cad[key]) > 32 or any(not isinstance(layer, str) or not 1 <= len(layer) <= 120 for layer in cad[key]) for key in ("wall_layers", "obstacle_layers")):
                raise ValueError("invalid CAD layers")
            if any(not isinstance(cad[key], int) or isinstance(cad[key], bool) or cad[key] < 0 for key in ("unsupported_entities", "malformed_entities")):
                raise ValueError("invalid CAD counters")
        economics = patch.get("economics", {})
        allowed_economics = {"staff_count", "monthly_employer_cost", "workdays_year", "hours_shift",
                             "human_tasks_shift", "task_share", "workload_day", "realization_share",
                             "robot_price", "integration_cost", "annual_service", "annual_energy",
                             "discount_rate", "operation_seconds"}
        if not isinstance(economics, dict) or set(economics) - allowed_economics:
            raise ValueError("invalid live economics fields")
        for key, value in economics.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0 or (key in {"task_share", "realization_share", "discount_rate"} and value > 1):
                raise ValueError("invalid live economics value")
        assignments = patch.get("assignments", [])
        if not isinstance(assignments, list) or len(assignments) > 64:
            raise ValueError("invalid assignments")
        assigned_robots = set()
        for assignment in assignments:
            if not isinstance(assignment, dict) or set(assignment) != {"robot_id", "charge_id", "work_id", "dropoff_id", "payload_kg", "speed_mps"}:
                raise ValueError("invalid assignment fields")
            if any(not isinstance(assignment[key], str) or not assignment[key] for key in ("robot_id", "charge_id", "work_id", "dropoff_id")):
                raise ValueError("invalid assignment references")
            if assignment["robot_id"] in assigned_robots:
                raise ValueError("duplicate robot assignment")
            assigned_robots.add(assignment["robot_id"])
            for field, lower, upper in (("payload_kg", 0, 2000), ("speed_mps", .1, 3)):
                value = assignment[field]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not lower <= value <= upper:
                    raise ValueError(f"invalid assignment {field}")
        if not isinstance(base.get("config"), dict) or not isinstance(base["config"].get("template"), str) or not isinstance(base["config"].get("seed"), str):
            raise ValueError("invalid scene config")
        zones = patch.get("zones", [])
        if not isinstance(zones, list) or len(zones) > 64:
            raise ValueError("invalid visual zones")
        zone_ids = set()
        width, depth = base["config"].get("width"), base["config"].get("depth")
        for zone in zones:
            if not isinstance(zone, dict) or set(zone) not in ({"id", "name", "points"}, {"id", "name", "points", "operational_role"}):
                raise ValueError("invalid visual zone fields")
            if "operational_role" in zone and zone["operational_role"] != "WORK":
                raise ValueError("invalid visual zone operational role")
            try:
                zone_id = str(uuid.UUID(zone["id"].removeprefix("zone:")))
            except (TypeError, ValueError, KeyError, AttributeError):
                raise ValueError("invalid visual zone ID") from None
            if zone["id"] != f"zone:{zone_id}" or zone_id in zone_ids:
                raise ValueError("invalid or duplicate visual zone ID")
            zone_ids.add(zone_id)
            if not isinstance(zone["name"], str) or not zone["name"].strip() or len(zone["name"]) > 120:
                raise ValueError("invalid visual zone name")
            points = zone["points"]
            if not isinstance(points, list) or not 3 <= len(points) <= 64 or not all(_vector(point, 2) for point in points):
                raise ValueError("invalid visual zone polygon")
            if not all(isinstance(size, (int, float)) and not isinstance(size, bool) and math.isfinite(size) and size > 0 for size in (width, depth)):
                raise ValueError("invalid visual zone bounds")
            if any(abs(point[0]) > width / 2 or abs(point[1]) > depth / 2 for point in points):
                raise ValueError("visual zone is outside the scene")
            area2 = sum(point[0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * point[1]
                        for index, point in enumerate(points))
            if abs(area2) < 1:
                raise ValueError("visual zone has zero area")
            def cross(a, b, c):
                return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            for index, a in enumerate(points):
                b = points[(index + 1) % len(points)]
                if math.dist(a, b) < .1:
                    raise ValueError("visual zone has a short edge")
                for other in range(index + 2, len(points)):
                    if index == 0 and other == len(points) - 1:
                        continue
                    c, d = points[other], points[(other + 1) % len(points)]
                    if cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0:
                        raise ValueError("visual zone has crossing edges")
        for field in ("objects", "robots"):
            if not isinstance(patch.get(field), dict):
                raise ValueError(f"ScenePatch {field} must be an object")
        for field in ("created", "deleted"):
            if not isinstance(patch.get(field), list):
                raise ValueError(f"ScenePatch {field} must be a list")
        if len(patch["created"]) > 2000 or len(patch["deleted"]) > 2000:
            raise ValueError("scene object limit exceeded")
        ids = [item.get("id") for item in patch["created"] if isinstance(item, dict)]
        if len(ids) != len(patch["created"]) or any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("created object IDs must be unique strings")
        rooms = patch.get("rooms", [])
        if not isinstance(rooms, list) or len(rooms) > 64:
            raise ValueError("invalid rooms")
        room_ids = set()
        linked_room_walls = set()
        created_walls = {item["id"] for item in patch["created"] if item.get("type") == "wall"}
        for room in rooms:
            if not isinstance(room, dict) or set(room) not in ({"id", "name", "points", "wall_ids"},
                                                               {"id", "name", "points", "wall_ids", "doors"}):
                raise ValueError("invalid room fields")
            try:
                room_uuid = str(uuid.UUID(room["id"].removeprefix("room:")))
            except (TypeError, ValueError, KeyError, AttributeError):
                raise ValueError("invalid room ID") from None
            if room["id"] != f"room:{room_uuid}" or room_uuid in room_ids:
                raise ValueError("invalid or duplicate room ID")
            room_ids.add(room_uuid)
            if not isinstance(room["name"], str) or not room["name"].strip() or len(room["name"]) > 120:
                raise ValueError("invalid room name")
            points, wall_ids = room["points"], room["wall_ids"]
            if not isinstance(points, list) or not 3 <= len(points) <= 64 or not all(_vector(point, 2) for point in points):
                raise ValueError("invalid room polygon")
            if not isinstance(wall_ids, list) or len(wall_ids) != len(points) or len(set(wall_ids)) != len(wall_ids) or any(wall_id not in created_walls for wall_id in wall_ids):
                raise ValueError("invalid room wall references")
            if any(wall_id in linked_room_walls or wall_id in patch["objects"] for wall_id in wall_ids):
                raise ValueError("room wall changed separately or belongs to multiple rooms")
            linked_room_walls.update(wall_ids)
            doors = room.get("doors", [])
            if not isinstance(doors, list) or len(doors) > len(points):
                raise ValueError("invalid room doors")
            used_edges = set()
            for door in doors:
                if not isinstance(door, dict) or set(door) != {"edge", "right_wall_id", "frame_id"}:
                    raise ValueError("invalid room door fields")
                edge = door["edge"]
                if not isinstance(edge, int) or isinstance(edge, bool) or not 0 <= edge < len(points) or edge in used_edges:
                    raise ValueError("invalid room door edge")
                used_edges.add(edge)
                for key, kind in (("right_wall_id", "wall"), ("frame_id", "door_frame")):
                    part_id = door[key]
                    if (not isinstance(part_id, str) or part_id in linked_room_walls or part_id in patch["objects"] or
                            not any(item["id"] == part_id and item.get("kind") == kind for item in patch["created"])):
                        raise ValueError("invalid room door parts")
                    linked_room_walls.add(part_id)
            if not all(isinstance(size, (int, float)) and not isinstance(size, bool) and math.isfinite(size) and size > 0 for size in (width, depth)):
                raise ValueError("invalid room bounds")
            if any(abs(point[0]) > width / 2 or abs(point[1]) > depth / 2 for point in points):
                raise ValueError("room is outside the scene")
            area2 = sum(point[0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * point[1]
                        for index, point in enumerate(points))
            if abs(area2) < 1:
                raise ValueError("room has zero area")
            for index, a in enumerate(points):
                b = points[(index + 1) % len(points)]
                if math.dist(a, b) < .5:
                    raise ValueError("room has a short edge")
                for other in range(index + 2, len(points)):
                    if index == 0 and other == len(points) - 1:
                        continue
                    c, d = points[other], points[(other + 1) % len(points)]
                    cross = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
                    if cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0:
                        raise ValueError("room has crossing edges")
        for item in patch["created"]:
            if set(item) - {"id", "instance_id", "kind", "editorId", "editorKind", "type", "position", "scale", "yaw", "color", "meta", "solid", "operational_role"}:
                raise ValueError("unknown created object fields")
            if not all(isinstance(item.get(field), str) and item[field] for field in ("kind", "type", "editorId", "editorKind")):
                raise ValueError("invalid created object type")
            if not _vector(item.get("position"), 3) or not _vector(item.get("scale"), 3) or any(value <= 0 for value in item["scale"]):
                raise ValueError("invalid created object geometry")
            if not isinstance(item.get("yaw", 0), (int, float)) or isinstance(item.get("yaw", 0), bool) or not math.isfinite(item.get("yaw", 0)):
                raise ValueError("invalid created object yaw")
            if "color" in item and not _vector(item["color"], 3):
                raise ValueError("invalid created object color")
            if "solid" in item and not isinstance(item["solid"], bool):
                raise ValueError("invalid created object solid flag")
            if "operational_role" in item:
                kind = item["kind"]
                allowed = {"CHARGE"} if kind in {"charger", "charging_dock"} else (
                    {"WORK", "DROPOFF"} if kind in {"station", "conveyor", "nurse_desk", "cargo", "pallet_stack", "baggage_cart", "hospital_cart", "painted_floor_marker"} else set())
                if item["operational_role"] not in allowed:
                    raise ValueError("invalid created object operational role")
        if any(not isinstance(item, str) for item in patch["deleted"]):
            raise ValueError("deleted IDs must be strings")
        for change in patch["objects"].values():
            if not isinstance(change, dict) or set(change) - {"position", "scale", "yaw"}:
                raise ValueError("invalid object update")
            if "position" in change and not _vector(change["position"], 3):
                raise ValueError("invalid object position")
            if "scale" in change and (not _vector(change["scale"], 3) or any(value <= 0 for value in change["scale"])):
                raise ValueError("invalid object scale")
            if "yaw" in change and (not isinstance(change["yaw"], (int, float)) or not math.isfinite(change["yaw"])):
                raise ValueError("invalid object yaw")
        for edit in patch["robots"].values():
            if not isinstance(edit, dict) or set(edit) - {"robotType", "points", "chargePosition", "startPosition"}:
                raise ValueError("invalid robot edit")
            if "robotType" in edit and not isinstance(edit["robotType"], str):
                raise ValueError("invalid robot type")
            if "points" in edit and (not isinstance(edit["points"], list) or any(not _vector(point, 2) for point in edit["points"])):
                raise ValueError("invalid robot points")
            for field in ("chargePosition", "startPosition"):
                if field in edit and not _vector(edit[field], 2):
                    raise ValueError("invalid robot position")
        inventory = document.get("inventory")
        if inventory is not None:
            if not isinstance(inventory, dict) or set(inventory) != {"slots", "active"}:
                raise ValueError("invalid inventory")
            if not isinstance(inventory["slots"], list) or len(inventory["slots"]) != 9 or any(item is not None and not isinstance(item, str) for item in inventory["slots"]):
                raise ValueError("invalid inventory slots")
            if inventory["active"] is not None and (not isinstance(inventory["active"], int) or not 0 <= inventory["active"] <= 8):
                raise ValueError("invalid active slot")
        if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("RobCraft document exceeds size limit")
        return self


def create_robcraft_scene_router() -> APIRouter:
    router = APIRouter(prefix="/api/projects")

    def owned(db: Session, project_id: uuid.UUID, context: AuthContext, *, lock: bool = False) -> Project:
        query = select(Project).where(Project.id == project_id, Project.owner_id == context.user.id,
                                      Project.status == "ACTIVE")
        project = db.scalar(query.with_for_update() if lock else query)
        if project is None:
            raise HTTPException(404, "project not found")
        return project

    @router.get("/{project_id}/robcraft-scene")
    def read(project_id: uuid.UUID, context: AuthContext = AUTH, db: Session = DB):
        state = (owned(db, project_id, context).profile or {}).get(PROFILE_KEY) or {}
        versions = state.get("versions") or []
        return {"revision": state.get("revision", 0), "name": state.get("name"),
                "document": deepcopy(versions[-1]["document"]) if versions else None,
                "versions": [{"revision": item["revision"], "name": item["name"], "saved_at": item["saved_at"]}
                             for item in versions]}

    @router.get("/{project_id}/robcraft-scene/versions/{revision}")
    def read_version(project_id: uuid.UUID, revision: int, context: AuthContext = AUTH, db: Session = DB):
        state = (owned(db, project_id, context).profile or {}).get(PROFILE_KEY) or {}
        version = next((item for item in state.get("versions", []) if item["revision"] == revision), None)
        if version is None:
            raise HTTPException(404, "RobCraft version not found")
        return deepcopy(version)

    @router.put("/{project_id}/robcraft-scene")
    def save(project_id: uuid.UUID, payload: SaveRobCraftScene,
             context: AuthContext = CSRF, db: Session = DB):
        project = owned(db, project_id, context, lock=True)
        state = deepcopy((project.profile or {}).get(PROFILE_KEY)) or {"revision": 0, "versions": []}
        if payload.expected_revision != state["revision"]:
            raise HTTPException(409, {"message": "RobCraft scene revision conflict", "current_revision": state["revision"]})
        revision = state["revision"] + 1
        name = payload.name.strip()
        if not name:
            raise HTTPException(422, "scene name is empty")
        version = {"revision": revision, "name": name,
                   "saved_at": datetime.now(timezone.utc).isoformat(), "document": deepcopy(payload.document)}
        state = {"revision": revision, "name": name,
                 "versions": [*state["versions"], version][-MAX_VERSIONS:]}
        project.profile = {**(project.profile or {}), PROFILE_KEY: state}
        db.commit()
        return {"revision": revision, "name": name, "saved_at": version["saved_at"]}

    @router.post("/{project_id}/robcraft-scene/save-as", status_code=201)
    def save_as(project_id: uuid.UUID, payload: SaveRobCraftScene,
                context: AuthContext = CSRF, db: Session = DB):
        source = owned(db, project_id, context, lock=True)
        source_revision = ((source.profile or {}).get(PROFILE_KEY) or {}).get("revision", 0)
        if payload.expected_revision != source_revision:
            raise HTTPException(409, {"message": "RobCraft scene revision conflict", "current_revision": source_revision})
        name = payload.name.strip()
        if not name:
            raise HTTPException(422, "scene name is empty")
        new_id = uuid.uuid4()
        saved_at = datetime.now(timezone.utc).isoformat()
        version = {"revision": 1, "name": name, "saved_at": saved_at,
                   "document": deepcopy(payload.document)}
        project = Project(id=new_id, owner_id=context.user.id, name=name,
                          copied_from_project_id=project_id, description=None,
                          profile={PROFILE_KEY: {"revision": 1, "name": name, "versions": [version]}},
                          status="ACTIVE")
        db.add(project)
        for slot, scenario_name in SCENARIO_SLOTS:
            db.add(Scenario(id=uuid.uuid4(), project_id=new_id, slot=slot,
                            name=scenario_name, inputs={}))
        db.commit()
        return {"project_id": new_id, "revision": 1, "name": name, "saved_at": saved_at}

    return router
