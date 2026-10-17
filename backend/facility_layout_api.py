"""Immutable, user-authored floorplan evidence bound to a saved capacity run.

The floorplan is not fed to the physical simulator. Only the explicitly applied
route distance in the already saved capacity input can affect calculations.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from auth import AuthContext, require_auth_context, require_csrf
from calculation_contracts import semantic_digest
from database import database_session
from fastapi import APIRouter, Depends, HTTPException
from persistence_models import AnalysisRun, Project
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

KEY = "facility_layout_v1"
MAX_SNAPSHOTS = 50
AUTH = Depends(require_auth_context)
CSRF = Depends(require_csrf)
DB = Depends(database_session)


class LayoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["rack", "obstacle", "no_go", "aisle", "charger", "pickup", "dropoff",
                  "receiving", "picking", "packing", "shipping", "staging"]
    x: float = Field(ge=0, le=500)
    y: float = Field(ge=0, le=500)
    width_m: float = Field(gt=0, le=500)
    depth_m: float = Field(gt=0, le=500)
    provenance: Literal["DRAWN", "PROVIDED", "ASSUMED"]


class FacilityLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["facility-layout-v1"]
    source: Literal["DRAWN", "IMAGE_REFERENCE", "DXF_TRACE", "ASSUMED_REFERENCE", "ASSUMED", "JSON_DRAFT"]
    width_m: float = Field(ge=10, le=500)
    depth_m: float = Field(ge=10, le=500)
    robot_width_m: float = Field(ge=.5, le=3)
    items: list[LayoutItem] = Field(min_length=2, max_length=400)
    reference_note: str | None = Field(default=None, max_length=500)
    image_not_embedded: bool = False

    @model_validator(mode="after")
    def verify_geometry(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("object identifiers must be unique")
        for item in self.items:
            if item.x + item.width_m > self.width_m or item.y + item.depth_m > self.depth_m:
                raise ValueError(f"{item.id} exceeds facility bounds")
        if sum(item.kind == "pickup" for item in self.items) != 1 or sum(item.kind == "dropoff" for item in self.items) != 1:
            raise ValueError("exactly one pickup and one dropoff are required")
        return self


class SaveLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layout: FacilityLayout
    applied_distance_m: Decimal = Field(gt=0, le=5000)
    process_id: str = Field(min_length=1, max_length=200)


def _normalized_run_distance(run: AnalysisRun, process_id: str) -> Decimal:
    snapshot = run.input_snapshot or {}
    process = snapshot.get("process") or {}
    if process.get("process_id") != process_id:
        raise HTTPException(422, "plan process does not match the saved capacity input")
    value = (process.get("route_distance") or {}).get("normalized_value")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(422, "saved capacity input has no route distance") from None


def create_facility_layout_router() -> APIRouter:
    router = APIRouter(prefix="/api/facility-layout")

    def owned(db: Session, project_id: uuid.UUID, context: AuthContext, lock: bool = False) -> Project:
        query = select(Project).where(Project.id == project_id, Project.owner_id == context.user.id,
                                      Project.status == "ACTIVE")
        project = db.scalar(query.with_for_update() if lock else query)
        if project is None:
            raise HTTPException(404, "project not found")
        return project

    def bound_run(db: Session, project_id: uuid.UUID, run_id: uuid.UUID) -> AnalysisRun:
        run = db.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id,
                                                  AnalysisRun.project_id == project_id,
                                                  AnalysisRun.run_kind == "CAPACITY_ANALYSIS",
                                                  AnalysisRun.status == "SUCCEEDED"))
        if run is None:
            raise HTTPException(404, "capacity run not found")
        return run

    @router.get("/projects/{project_id}/runs/{run_id}")
    def read(project_id: uuid.UUID, run_id: uuid.UUID, context: AuthContext = AUTH, db: Session = DB):
        project = owned(db, project_id, context)
        run = bound_run(db, project_id, run_id)
        state = (project.profile or {}).get(KEY) or {"snapshots": []}
        snapshot = next((item for item in state["snapshots"] if item["capacity_run_id"] == str(run_id)), None)
        if snapshot is None:
            raise HTTPException(404, "no floorplan bound to this run")
        if snapshot["capacity_input_sha256"] != run.input_sha256 or snapshot["capacity_result_sha256"] != run.result_sha256:
            raise HTTPException(409, "capacity run changed after floorplan binding")
        return {"snapshot": snapshot}

    @router.post("/projects/{project_id}/runs/{run_id}")
    def save(project_id: uuid.UUID, run_id: uuid.UUID, payload: SaveLayout,
             context: AuthContext = CSRF, db: Session = DB):
        project = owned(db, project_id, context, lock=True)
        run = bound_run(db, project_id, run_id)
        if _normalized_run_distance(run, payload.process_id) != payload.applied_distance_m:
            raise HTTPException(422, "applied distance does not match the saved capacity input")
        state = deepcopy((project.profile or {}).get(KEY)) or {"schema_version": "facility-layout-evidence-v1", "snapshots": []}
        previous = next((item for item in state["snapshots"] if item["capacity_run_id"] == str(run_id)), None)
        layout = payload.layout.model_dump(mode="json")
        digest = semantic_digest(layout)
        if previous:
            if previous["layout_digest"] != digest:
                raise HTTPException(409, "this capacity run already has a different floorplan")
            return {"snapshot": previous}
        if len(state["snapshots"]) >= MAX_SNAPSHOTS:
            raise HTTPException(429, "floorplan evidence limit reached")
        snapshot = {"schema_version": "facility-layout-evidence-v1", "capacity_run_id": str(run_id),
                    "capacity_input_sha256": run.input_sha256, "capacity_result_sha256": run.result_sha256,
                    "process_id": payload.process_id, "applied_distance_m": str(payload.applied_distance_m),
                    "layout": layout, "layout_digest": digest, "status": "USER_ROUTE_ESTIMATE_GEOMETRY_UNVERIFIED",
                    "created_at": datetime.now(timezone.utc).isoformat()}
        state["snapshots"].append(snapshot)
        project.profile = {**(project.profile or {}), KEY: state}
        db.commit()
        return {"snapshot": snapshot}

    return router
