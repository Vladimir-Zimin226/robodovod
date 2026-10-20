"""Versioned, owner-bound warehouse role scenario API."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone

from auth import AuthContext, require_auth_context, require_csrf
from calculation.warehouse_roles import WarehouseRoleInput, analyze_warehouse_roles, warehouse_template
from calculation.role_report import role_report_pdf
from catalog_repository import CatalogSnapshotDTO
from database import database_session
from fastapi import APIRouter, Depends, HTTPException, Response
from persistence_api import _audit, _canonical_sha256, _owned_project
from persistence_models import Project
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

KEY = "warehouse_role_scenarios_v1"
MAX_VERSIONS = 100


class SaveWarehouseRoles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    expected_catalog_version: str
    input: WarehouseRoleInput


class WarehouseRolePdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_catalog_version: str
    input: WarehouseRoleInput
    what_if_input: WarehouseRoleInput | None = None
    scene_snapshots: dict[str, str | None] | None = None


def create_warehouse_roles_router(discovery_loader: Callable[[], CatalogSnapshotDTO]) -> APIRouter:
    router = APIRouter(prefix="/api/v2")

    @router.get("/warehouse-roles/template")
    def template():
        return warehouse_template()

    @router.post("/warehouse-roles/preview")
    def guest_preview(payload: WarehouseRoleInput):
        try:
            return analyze_warehouse_roles(payload, discovery_loader())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/warehouse-roles/report.pdf")
    def guest_report(payload: WarehouseRolePdfRequest):
        catalog = discovery_loader()
        if payload.expected_catalog_version != catalog.version.code:
            raise HTTPException(409, "active catalog changed; preview again")
        try:
            result = analyze_warehouse_roles(payload.input, catalog)
            comparison = analyze_warehouse_roles(payload.what_if_input, catalog) if payload.what_if_input else None
            pdf = role_report_pdf(result, comparison, payload.scene_snapshots)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(pdf, media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="robodovod-warehouse-scenario.pdf"'})

    @router.get("/projects/{project_id}/warehouse-roles")
    def latest(project_id: uuid.UUID,
               context: AuthContext = Depends(require_auth_context),
               db: Session = Depends(database_session)):
        project = _owned_project(db, project_id, context.user.id)
        state = (project.profile or {}).get(KEY) or {"version": 0, "versions": []}
        saved = deepcopy(state["versions"][-1]) if state["versions"] else None
        if saved and (_canonical_sha256(saved["input_snapshot"]) != saved["input_sha256"] or
                      _canonical_sha256(saved["result_snapshot"]) != saved["result_sha256"]):
            raise HTTPException(409, "warehouse role scenario integrity check failed")
        return {"version": state["version"], "latest": saved}

    @router.post("/projects/{project_id}/warehouse-roles/preview")
    def preview(project_id: uuid.UUID, payload: WarehouseRoleInput,
                context: AuthContext = Depends(require_csrf),
                db: Session = Depends(database_session)):
        _owned_project(db, project_id, context.user.id)
        return guest_preview(payload)

    @router.post("/projects/{project_id}/warehouse-roles")
    def save(project_id: uuid.UUID, payload: SaveWarehouseRoles,
             context: AuthContext = Depends(require_csrf),
             db: Session = Depends(database_session)):
        project = db.scalar(select(Project).where(Project.id == project_id,
            Project.owner_id == context.user.id, Project.status == "ACTIVE").with_for_update())
        if project is None:
            raise HTTPException(404, "project not found")
        state = deepcopy((project.profile or {}).get(KEY)) or {"version": 0, "versions": []}
        if payload.expected_version != state["version"]:
            raise HTTPException(409, "warehouse role scenario changed; reload before saving")
        if len(state["versions"]) >= MAX_VERSIONS:
            raise HTTPException(429, "warehouse role scenario version limit reached")
        catalog = discovery_loader()
        if payload.expected_catalog_version != catalog.version.code:
            raise HTTPException(409, "active catalog changed; preview again")
        try:
            result = analyze_warehouse_roles(payload.input, catalog)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        input_snapshot = payload.input.model_dump(mode="json")
        result_snapshot = result
        saved = {"id": str(uuid.uuid4()), "version": state["version"] + 1,
                 "created_at": datetime.now(timezone.utc).isoformat(),
                 "input_snapshot": input_snapshot, "result_snapshot": result_snapshot,
                 "input_sha256": _canonical_sha256(input_snapshot),
                 "result_sha256": _canonical_sha256(result_snapshot)}
        state["version"] = saved["version"]
        state["versions"].append(saved)
        project.profile = {**(project.profile or {}), KEY: state}
        _audit(db, "WAREHOUSE_ROLE_SCENARIO_SAVED", actor_id=context.user.id,
               project_id=project_id,
               aggregate={"run_id": saved["id"], "version": saved["version"],
                          "role_count": len(payload.input.roles), "catalog_version": catalog.version.code})
        db.commit()
        return {"version": state["version"], "latest": saved}

    return router
