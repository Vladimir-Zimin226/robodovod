"""ADMIN/CSRF/owner guarded catalog lifecycle, import, audit and atomic rollback."""

from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import replace
from typing import Literal

from admin_catalog import (
    FORMAT,
    MAX_BYTES,
    Contract,
    diff,
    digest,
    export_document,
    project_document,
    validate_document,
)
from admin_catalog_models import AdminCatalogDocument
from auth import AuthContext, require_admin, require_csrf, utcnow
from catalog_activation import catalog_activation_status
from catalog_capacity_rollout import (
    CapacityRolloutPolicyError,
    validate_capacity_source,
)
from catalog_repository import CatalogVersionDTO, PostgresCatalogRepository
from catalog_runtime import CatalogRuntime
from database import database_session, get_database
from fastapi import APIRouter, Depends, HTTPException, Request
from persistence_models import AuditEntry
from pydantic import Field, ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from storage_models import CatalogActivation, CatalogVersion

router = APIRouter(prefix="/api/admin/catalog", tags=["admin-catalog"])
public_router = APIRouter(prefix="/api/catalog")
_PUBLIC_CATALOG_RUNTIME = CatalogRuntime()
ADMIN = Depends(require_admin)
DB = Depends(database_session)


CSRF = Depends(require_csrf)


def admin_csrf(context: AuthContext = CSRF):
    if context.user.role != "ADMIN":
        raise HTTPException(403, "administrator role required")
    return context


WRITE = Depends(admin_csrf)


@public_router.get("/defaults")
def defaults():
    snapshot = _PUBLIC_CATALOG_RUNTIME.load_discovery()
    return {
        "catalog_code": snapshot.version.code,
        "sha256": snapshot.version.content_sha256,
        "defaults": list(snapshot.admin_defaults),
        "requires_user_confirmation": True,
    }


class Create(Contract):
    code: str = Field(pattern="^[a-z0-9][a-z0-9._-]{2,100}$")
    parent_code: str


class Edit(Contract):
    expected_revision: int = Field(ge=1)
    document: dict


class Revision(Contract):
    expected_revision: int = Field(ge=1)


class SectionEdit(Contract):
    expected_revision: int = Field(ge=1)
    entries: list[dict] = Field(max_length=10000)


class Switch(Contract):
    expected_active: dict[str, str | None]
    slots: list[str] = Field(min_length=1, max_length=3)


def audit(db, context, event, code, **aggregate):
    db.add(
        AuditEntry(
            event_type="ADMIN_CATALOG_" + event,
            actor_user_id=context.user.id,
            aggregate={"catalog_code": code, **aggregate},
        )
    )


def version(db, code, *, lock=False):
    query = select(CatalogVersion).where(CatalogVersion.code == code)
    value = db.scalar(query.with_for_update() if lock else query)
    if value is None:
        raise HTTPException(404, "catalog version not found")
    return value


def editable(db, code, context, revision):
    value = version(db, code, lock=True)
    row = db.get(AdminCatalogDocument, value.id)
    if row is None or row.owner_id != context.user.id:
        raise HTTPException(
            403, "only the draft owner may edit or publish this version"
        )
    if value.status not in {"DRAFT", "VALIDATED"}:
        raise HTTPException(409, "published catalog is immutable; create a new draft")
    if row.revision != revision:
        raise HTTPException(409, "catalog revision changed; reload before editing")
    return value, row


def baseline(document):
    return PostgresCatalogRepository(
        get_database(), document["base_catalog_code"]
    ).load()


def validate(payload, reference):
    try:
        return validate_document(payload, reference)
    except (ValueError, ValidationError, ArithmeticError) as exc:
        raise HTTPException(
            422, "Invalid catalog document: " + str(exc)[:1000]
        ) from exc


def describe(db, value):
    row = db.get(AdminCatalogDocument, value.id)
    document = (
        copy.deepcopy(row.document)
        if row
        else export_document(
            PostgresCatalogRepository(get_database(), value.code).load()
        )
    )
    reference = baseline(document)
    projected = project_document(
        validate(document, reference),
        reference,
        CatalogVersionDTO(
            str(value.id),
            value.code,
            value.status,
            value.schema_version,
            value.content_sha256,
        ),
    )
    blockers = []
    try:
        validate_capacity_source(
            replace(projected, version=replace(projected.version, status="PUBLISHED"))
        )
    except CapacityRolloutPolicyError as exc:
        blockers.append(str(exc))
    comparison = export_document(reference)
    if value.parent_version_id:
        parent = db.get(CatalogVersion, value.parent_version_id)
        parent_doc = db.get(AdminCatalogDocument, parent.id)
        if parent_doc:
            comparison = parent_doc.document

    def completeness(model):
        required = sorted(
            {
                field.split(".", 1)[-1]
                for candidate in reference.models
                if candidate.system_family == model.system_family
                for field in candidate.capacity_runtime.calculation_model_fields
            }
        )
        specs = model.attributes.get("admin_metadata", {}).get("specifications", [])
        known = {
            spec["code"]
            for spec in specs
            if spec["value"] is not None
            and spec["status"] in {"VERIFIED_OFFICIAL", "MANUALLY_APPROVED"}
        }
        return {
            "required_specs": required,
            "missing_specs": sorted(set(required) - known),
            "completeness": "COMPLETE"
            if required and set(required) <= known
            else "UNKNOWN",
        }

    return {
        "code": value.code,
        "id": str(value.id),
        "status": value.status,
        "owner_id": str(row.owner_id) if row else None,
        "revision": row.revision if row else None,
        "document": document,
        "sha256": digest(document),
        "diff": diff(comparison, document),
        "capacity_activation_ready": not blockers,
        "runtime_activation_ready": bool(projected.runtime_robots()),
        "capacity_activation_blockers": blockers,
        "calculation_ready_positions": len(projected.calculation_ready_positions()),
        "model_readiness": [
            {
                "key": model.source_record_key,
                "ready": model.capacity_runtime.calculation_ready,
                "blockers": list(model.capacity_runtime.calculation_blockers),
                **completeness(model),
                "known_specs": sum(
                    spec["value"] is not None
                    for spec in model.attributes.get("admin_metadata", {}).get(
                        "specifications", []
                    )
                ),
            }
            for model in projected.models
        ],
    }


@router.get("")
def listing(_context: AuthContext = ADMIN, db: Session = DB):
    return {
        "versions": [
            {"code": item.code, "status": item.status, "sha256": item.content_sha256}
            for item in db.scalars(
                select(CatalogVersion).order_by(CatalogVersion.created_at.desc())
            )
        ],
        **catalog_activation_status(get_database()),
    }


@router.get("/audit")
def history(_context: AuthContext = ADMIN, db: Session = DB):
    rows = db.scalars(
        select(AuditEntry)
        .where(AuditEntry.event_type.like("ADMIN_CATALOG_%"))
        .order_by(AuditEntry.created_at.desc(), AuditEntry.id)
        .limit(200)
    ).all()
    return {
        "entries": [
            {
                "actor": str(item.actor_user_id),
                "at": item.created_at.isoformat(),
                "event": item.event_type,
                "change": item.aggregate,
            }
            for item in rows
        ]
    }


@router.get("/versions/{code}")
def read(code: str, _context: AuthContext = ADMIN, db: Session = DB):
    return describe(db, version(db, code))


def create_draft(db, context, code, parent_code, document=None, import_sha=None):
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,100}", code):
        raise HTTPException(422, "invalid catalog version code")
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": "admin-catalog:" + code},
    )
    existing = db.scalar(select(CatalogVersion).where(CatalogVersion.code == code))
    if existing:
        row = db.get(AdminCatalogDocument, existing.id)
        if (
            import_sha
            and row
            and row.import_sha256 == import_sha
            and row.owner_id == context.user.id
        ):
            return {**describe(db, existing), "idempotent": True}
        raise HTTPException(409, "catalog code already exists")
    parent = version(db, parent_code)
    if parent.status != "PUBLISHED":
        raise HTTPException(422, "draft requires a published parent")
    inherited = db.get(AdminCatalogDocument, parent.id)
    parent_document = (
        copy.deepcopy(inherited.document)
        if inherited
        else export_document(
            PostgresCatalogRepository(get_database(), parent_code).load()
        )
    )
    document = document or parent_document
    if (document.get("base_catalog_code"), document.get("base_content_sha256")) != (
        parent_document["base_catalog_code"],
        parent_document["base_content_sha256"],
    ):
        raise HTTPException(422, "import parent binding mismatch")
    document = validate(document, baseline(parent_document)).model_dump(mode="json")
    value = CatalogVersion(
        id=uuid.uuid4(),
        code=code,
        parent_version_id=parent.id,
        status="DRAFT",
        schema_version=FORMAT,
    )
    db.add(value)
    db.flush()
    db.add(
        AdminCatalogDocument(
            catalog_version_id=value.id,
            owner_id=context.user.id,
            revision=1,
            document=document,
            import_sha256=import_sha,
        )
    )
    audit(
        db,
        context,
        "IMPORTED" if import_sha else "CREATED",
        code,
        parent=parent_code,
        sha256=digest(document),
        import_sha256=import_sha,
    )
    db.commit()
    return {**describe(db, value), "idempotent": False}


@router.post("/versions", status_code=201)
def create(payload: Create, context: AuthContext = WRITE, db: Session = DB):
    return create_draft(db, context, payload.code, payload.parent_code)


@router.post("/import", status_code=201)
async def upload(request: Request, context: AuthContext = WRITE, db: Session = DB):
    # Stream with a hard bound; no ZIP extraction, formulas, URLs or document code run.
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(413, "catalog import exceeds 4 MiB")
        chunks.append(chunk)
    raw = b"".join(chunks)
    try:

        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON object key")
                value[key] = item
            return value

        payload = json.loads(raw, object_pairs_hook=unique_object)
        if set(payload) != {"code", "parent_code", "document"}:
            raise ValueError("expected code, parent_code, document")
        Create.model_validate(
            {"code": payload["code"], "parent_code": payload["parent_code"]}
        )
        import_sha = digest(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "invalid admin-catalog-v1 JSON file") from exc
    return create_draft(
        db,
        context,
        payload["code"],
        payload["parent_code"],
        payload["document"],
        import_sha,
    )


@router.put("/versions/{code}")
def update(code: str, payload: Edit, context: AuthContext = WRITE, db: Session = DB):
    value, row = editable(db, code, context, payload.expected_revision)
    document = validate(payload.document, baseline(row.document)).model_dump(
        mode="json"
    )
    changes = diff(row.document, document)
    if changes:
        # VALIDATED cannot transition back to DRAFT in the accepted lifecycle.
        # Validation is re-run at publication and digest/revision invalidates previews.
        row.document = document
        row.revision += 1
        value.content_sha256 = None
        value.updated_at = utcnow()
        audit(
            db,
            context,
            "EDITED",
            code,
            revision=row.revision,
            changes=changes,
            sha256=digest(document),
        )
        db.commit()
    return describe(db, value)


@router.get("/versions/{code}/sections/{section}")
def read_section(
    code: str,
    section: Literal["models", "offers", "sources", "defaults", "dictionaries"],
    _context: AuthContext = ADMIN,
    db: Session = DB,
):
    result = describe(db, version(db, code))
    return {
        "code": code,
        "revision": result["revision"],
        "entries": result["document"][section],
    }


@router.put("/versions/{code}/sections/{section}")
def write_section(
    code: str,
    section: Literal["models", "offers", "sources", "defaults", "dictionaries"],
    payload: SectionEdit,
    context: AuthContext = WRITE,
    db: Session = DB,
):
    _, row = editable(db, code, context, payload.expected_revision)
    document = copy.deepcopy(row.document)
    document[section] = payload.entries
    return update(
        code,
        Edit(expected_revision=payload.expected_revision, document=document),
        context,
        db,
    )


@router.post("/versions/{code}/validate")
def check(code: str, payload: Revision, context: AuthContext = WRITE, db: Session = DB):
    value, row = editable(db, code, context, payload.expected_revision)
    validate(row.document, baseline(row.document))
    value.content_sha256 = digest(row.document)
    value.status = "VALIDATED"
    value.validated_at = utcnow()
    value.updated_at = utcnow()
    audit(
        db,
        context,
        "VALIDATED",
        code,
        revision=row.revision,
        sha256=value.content_sha256,
    )
    db.commit()
    return describe(db, value)


@router.post("/versions/{code}/publish")
def publish(
    code: str, payload: Revision, context: AuthContext = WRITE, db: Session = DB
):
    value, row = editable(db, code, context, payload.expected_revision)
    validate(row.document, baseline(row.document))
    if value.status != "VALIDATED" or value.content_sha256 != digest(row.document):
        raise HTTPException(409, "validate the current revision before publication")
    value.status = "PUBLISHED"
    value.published_at = utcnow()
    value.updated_at = utcnow()
    audit(
        db,
        context,
        "PUBLISHED",
        code,
        revision=row.revision,
        sha256=value.content_sha256,
    )
    db.commit()
    return describe(db, value)


@router.post("/versions/{code}/activate")
def activate(
    code: str, payload: Switch, context: AuthContext = WRITE, db: Session = DB
):
    slots = sorted(set(payload.slots))
    if len(slots) != len(payload.slots) or any(
        slot not in {"runtime", "discovery", "capacity"} for slot in slots
    ):
        raise HTTPException(422, "unsupported/duplicate activation slot")
    if set(payload.expected_active) != set(slots):
        raise HTTPException(422, "expected active version is required for every slot")
    # Lock all pointers in stable order, then resolve the immutable candidate. This
    # transaction includes the audit and prevents concurrent switches/lost rollback.
    for slot in slots:
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "robodovod:catalog-activation:" + slot},
        )
    value = version(db, code, lock=True)
    if value.status != "PUBLISHED":
        raise HTTPException(409, "activation requires a published version")
    snapshot = PostgresCatalogRepository(get_database(), code).load()
    if "runtime" in slots and not snapshot.runtime_robots():
        raise HTTPException(
            422, "runtime activation requires evidence-backed runtime positions"
        )
    if "capacity" in slots:
        try:
            validate_capacity_source(snapshot)
        except CapacityRolloutPolicyError as exc:
            raise HTTPException(422, str(exc)) from exc
    changed = []
    for slot in slots:
        current = db.scalar(
            select(CatalogActivation)
            .where(
                CatalogActivation.slot == slot,
                CatalogActivation.deactivated_at.is_(None),
            )
            .with_for_update()
        )
        previous = (
            db.get(CatalogVersion, current.catalog_version_id) if current else None
        )
        if (previous.code if previous else None) != payload.expected_active[slot]:
            raise HTTPException(
                409, "active catalog changed; reload before activation/rollback"
            )
        if previous and previous.id == value.id:
            continue
        now = utcnow()
        if current:
            current.deactivated_at = now
            db.flush()
        proof = digest(
            {
                "candidate": code,
                "sha256": snapshot.version.content_sha256,
                "root": snapshot.rollout_reference.version.code
                if snapshot.rollout_reference
                else code,
                "gate": "unchanged-approved-physical-projection-v1",
            }
        )
        db.add(
            CatalogActivation(
                id=uuid.uuid4(),
                slot=slot,
                catalog_version_id=value.id,
                activated_at=now,
                actor_subject=str(context.user.id),
                rollout_policy_version="admin-inherited-capacity-rollout-v1"
                if slot == "capacity"
                else None,
                approval_report_sha256=proof if slot == "capacity" else None,
                rollback_mode=("RESTORE_VERSION" if previous else "DEACTIVATE")
                if slot == "capacity"
                else None,
                rollback_catalog_version_id=previous.id
                if previous and slot == "capacity"
                else None,
            )
        )
        changed.append(
            {"slot": slot, "before": previous.code if previous else None, "after": code}
        )
    if changed:
        audit(db, context, "ACTIVATED", code, changes=changed)
        db.commit()
    return {"changed": changed, **catalog_activation_status(get_database())}
