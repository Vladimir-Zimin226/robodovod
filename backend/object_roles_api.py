"""Owner-bound object role scenarios with immutable snapshots and optimistic locking."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import AuthContext, require_auth_context, require_csrf
from calculation.object_roles import ObjectRoleInput, analyze_object_roles, object_template
from catalog_repository import CatalogSnapshotDTO
from database import database_session
from persistence_api import _audit, _canonical_sha256, _owned_project
from persistence_models import Project

MAX_VERSIONS = 100


class SaveObjectRoles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    expected_catalog_version: str
    input: ObjectRoleInput


def _key(kind: str) -> str:
    if kind not in {"WAREHOUSE", "AIRPORT", "CLINIC"}:
        raise HTTPException(404, "unknown object kind")
    return f"object_role_scenarios_v2_{kind.lower()}"


def create_object_roles_router(discovery_loader: Callable[[], CatalogSnapshotDTO]) -> APIRouter:
    router = APIRouter(prefix="/api/v2")

    @router.get("/object-roles/{kind}/template")
    def template(kind: str):
        _key(kind)
        return object_template(kind)

    @router.get("/projects/{project_id}/object-roles/{kind}")
    def latest(project_id: uuid.UUID, kind: str,
               context: AuthContext = Depends(require_auth_context),
               db: Session = Depends(database_session)):
        project = _owned_project(db, project_id, context.user.id)
        state = (project.profile or {}).get(_key(kind)) or {"version": 0, "versions": []}
        saved = deepcopy(state["versions"][-1]) if state["versions"] else None
        if saved and (_canonical_sha256(saved["input_snapshot"]) != saved["input_sha256"] or
                      _canonical_sha256(saved["result_snapshot"]) != saved["result_sha256"]):
            raise HTTPException(409, "object role scenario integrity check failed")
        return {"version": state["version"], "latest": saved}

    @router.post("/projects/{project_id}/object-roles/{kind}/preview")
    def preview(project_id: uuid.UUID, kind: str, payload: ObjectRoleInput,
                context: AuthContext = Depends(require_csrf),
                db: Session = Depends(database_session)):
        _key(kind)
        _owned_project(db, project_id, context.user.id)
        if payload.kind != kind:
            raise HTTPException(422, "object kind mismatch")
        try:
            return analyze_object_roles(payload, discovery_loader())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/projects/{project_id}/object-roles/{kind}")
    def save(project_id: uuid.UUID, kind: str, payload: SaveObjectRoles,
             context: AuthContext = Depends(require_csrf),
             db: Session = Depends(database_session)):
        key = _key(kind)
        if payload.input.kind != kind:
            raise HTTPException(422, "object kind mismatch")
        project = db.scalar(select(Project).where(Project.id == project_id,
            Project.owner_id == context.user.id, Project.status == "ACTIVE").with_for_update())
        if project is None:
            raise HTTPException(404, "project not found")
        state = deepcopy((project.profile or {}).get(key)) or {"version": 0, "versions": []}
        if payload.expected_version != state["version"]:
            raise HTTPException(409, "object role scenario changed; reload before saving")
        if len(state["versions"]) >= MAX_VERSIONS:
            raise HTTPException(429, "object role scenario version limit reached")
        catalog = discovery_loader()
        if payload.expected_catalog_version != catalog.version.code:
            raise HTTPException(409, "active catalog changed; preview again")
        try:
            result = analyze_object_roles(payload.input, catalog)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        inputs = payload.input.model_dump(mode="json")
        saved = {"id": str(uuid.uuid4()), "version": state["version"] + 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_snapshot": inputs, "result_snapshot": result,
            "input_sha256": _canonical_sha256(inputs), "result_sha256": _canonical_sha256(result)}
        state["version"] = saved["version"]
        state["versions"].append(saved)
        project.profile = {**(project.profile or {}), key: state}
        _audit(db, "OBJECT_ROLE_SCENARIO_SAVED", actor_id=context.user.id,
               project_id=project_id, aggregate={"run_id": saved["id"],
               "version": saved["version"], "kind": kind, "catalog_version": catalog.version.code})
        db.commit()
        return {"version": state["version"], "latest": saved}

    return router
