"""HTTP API for authentication, projects and persisted analysis snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from auth import (
    AuthContext,
    clear_session_cookies,
    create_session,
    hash_password,
    normalize_email,
    normalize_name,
    require_admin,
    require_auth_context,
    require_csrf,
    set_session_cookies,
    utcnow,
    validate_password,
    verify_password,
)
from database import database_session
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from models import CalculationResponse, UserInput
from persistence_models import (
    AnalysisRun,
    AuditEntry,
    Project,
    ProjectDeletionJob,
    ProjectFile,
    ProjectFileImport,
    Scenario,
    User,
    UserSession,
)
from project_file_intake import (
    MAX_FILE_BYTES,
    IntakeError,
    build_csv_template,
    inspect_project_file,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger("robomera.persistence")
SCENARIO_SLOTS = (
    ("BASE", "Базовый"),
    ("OPTIMISTIC", "Оптимистичный"),
    ("PESSIMISTIC", "Пессимистичный"),
)
RULES_VERSION = "legacy-calculation-rules-v1+readiness-rules-v1"
ECONOMICS_VERSION = "legacy-economics-v1"
OBJECT_PROFILE_VERSION = "user-input-v1"
APPLICATION_VERSION = "3.9.0"


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(ApiModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        try:
            return normalize_email(value)
        except ValueError as exc:
            raise ValueError("Некорректный email") from exc


class RegisterRequest(Credentials):
    name: str | None = None

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        try:
            validate_password(value)
        except ValueError as exc:
            raise ValueError("Пароль должен содержать от 12 до 128 символов") from exc
        return value

    @field_validator("name")
    @classmethod
    def name_policy(cls, value: str | None) -> str | None:
        try:
            return normalize_name(value)
        except ValueError as exc:
            raise ValueError("Имя должно содержать от 1 до 200 символов") from exc


class AdminCreateUserRequest(RegisterRequest):
    role: Literal["USER", "ADMIN"] = "USER"


class AdminUpdateUserRequest(ApiModel):
    name: str | None = None
    role: Literal["USER", "ADMIN"] | None = None
    status: Literal["ACTIVE", "DISABLED"] | None = None

    @field_validator("name")
    @classmethod
    def name_policy(cls, value: str | None) -> str | None:
        try:
            return normalize_name(value)
        except ValueError as exc:
            raise ValueError("Имя должно содержать от 1 до 200 символов") from exc


class PasswordResetRequest(ApiModel):
    password: str

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        try:
            validate_password(value)
        except ValueError as exc:
            raise ValueError("Пароль должен содержать от 12 до 128 символов") from exc
        return value


class ProjectCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    profile: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название не может быть пустым")
        return value


class ProjectUpdateRequest(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    profile: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Название не может быть пустым")
        return value


class ScenarioUpdateRequest(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    inputs: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Название не может быть пустым")
        return value


class AnalysisCreateRequest(ApiModel):
    scenario_id: uuid.UUID
    input: UserInput


def _user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email_normalized,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _scenario_dict(scenario: Scenario) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "slot": scenario.slot,
        "name": scenario.name,
        "inputs": scenario.inputs,
        "created_at": scenario.created_at,
        "updated_at": scenario.updated_at,
    }


def _project_dict(db: Session, project: Project) -> dict[str, Any]:
    scenarios = db.scalars(
        select(Scenario)
        .where(Scenario.project_id == project.id)
        .order_by(Scenario.slot)
    ).all()
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "profile": project.profile,
        "copied_from_project_id": project.copied_from_project_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "scenarios": [_scenario_dict(item) for item in scenarios],
    }


def _file_dict(db: Session, item: ProjectFile) -> dict[str, Any]:
    imported = db.scalar(
        select(ProjectFileImport).where(ProjectFileImport.project_file_id == item.id)
    )
    return {
        "id": item.id,
        "project_id": item.project_id,
        "original_name": item.original_name,
        "media_type": item.media_type,
        "byte_size": item.byte_size,
        "sha256": item.sha256,
        "created_at": item.created_at,
        "import": (
            {
                "id": imported.id,
                "scenario_id": imported.scenario_id,
                "profile_code": imported.profile_code,
                "file_format": imported.file_format,
                "profile_version": imported.profile_version,
                "parameter_values": imported.parameter_values,
                "parameter_provenance": imported.parameter_provenance,
                "normalized_input": imported.normalized_input,
                "provenance": imported.provenance,
                "validation_report": imported.validation_report,
                "applied_at": imported.applied_at,
            }
            if imported is not None
            else None
        ),
    }


def _run_dict(run: AnalysisRun, *, include_snapshots: bool) -> dict[str, Any]:
    value = {
        "id": run.id,
        "project_id": run.project_id,
        "scenario_id": run.scenario_id,
        "parent_run_id": run.parent_run_id,
        "status": run.status,
        "revision_id": run.revision_id,
        "versions": {
            "catalog": run.catalog_version_code,
            "rules": run.rules_version,
            "economics": run.economics_version,
            "object_profile": run.object_profile_version,
            "application": run.application_version,
        },
        "checksums": {
            "input": run.input_sha256,
            "result": run.result_sha256,
            "scenario_spec": run.scenario_spec_sha256,
        },
        "diagnostics": run.diagnostics,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
    if include_snapshots:
        value.update(
            {
                "input_snapshot": run.input_snapshot,
                "result_snapshot": run.result_snapshot,
                "scenario_spec_snapshot": run.scenario_spec_snapshot,
            }
        )
    return value


def _audit(
    db: Session,
    event_type: str,
    *,
    actor_id: uuid.UUID | None = None,
    subject_user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    aggregate: dict[str, Any] | None = None,
    retention_until: datetime | None = None,
) -> None:
    db.add(
        AuditEntry(
            id=uuid.uuid4(),
            event_type=event_type,
            actor_user_id=actor_id,
            subject_user_id=subject_user_id,
            project_subject_id=project_id,
            aggregate=aggregate or {},
            retention_until=retention_until,
        )
    )


def _owned_project(
    db: Session,
    project_id: uuid.UUID,
    owner_id: uuid.UUID,
    *,
    active_only: bool = True,
) -> Project:
    predicates = [Project.id == project_id, Project.owner_id == owner_id]
    if active_only:
        predicates.append(Project.status == "ACTIVE")
    project = db.scalar(select(Project).where(*predicates))
    if project is None:
        # Deliberately do not distinguish missing from another user's project.
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _storage_root() -> Path:
    return Path(os.getenv("PROJECT_FILE_STORAGE_ROOT", "data/uploads")).resolve()


def _storage_path(storage_key: str) -> Path:
    key_path = Path(storage_key)
    if key_path.is_absolute() or ".." in key_path.parts:
        raise ValueError("unsafe storage key")
    root = _storage_root()
    candidate = (root / key_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("unsafe storage key")
    return candidate


async def _read_project_upload(upload: UploadFile) -> bytes:
    payload = await upload.read(MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="FILE_TOO_LARGE")
    return payload


def _inspect_upload(filename: str | None, payload: bytes, profile_code: str):
    try:
        return inspect_project_file(filename or "", payload, profile_code)
    except IntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def delete_project(
    db: Session,
    project_id: uuid.UUID,
    owner_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    try:
        retention_days = int(os.getenv("DELETION_TOMBSTONE_DAYS", "30"))
    except ValueError:
        raise HTTPException(status_code=500, detail="project deletion is not configured") from None
    if retention_days < 1 or retention_days > 3650:
        raise HTTPException(status_code=500, detail="project deletion is not configured")
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.owner_id == owner_id)
        .with_for_update()
    )
    if project is None or project.status not in {"ACTIVE", "DELETING", "DELETE_FAILED"}:
        raise HTTPException(status_code=404, detail="project not found")

    files = db.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id)).all()
    scenario_count = db.scalar(
        select(func.count()).select_from(Scenario).where(Scenario.project_id == project.id)
    ) or 0
    run_count = db.scalar(
        select(func.count()).select_from(AnalysisRun).where(AnalysisRun.project_id == project.id)
    ) or 0
    storage_keys = [item.storage_key for item in files]
    project.status = "DELETING"
    project.updated_at = utcnow()
    job = db.scalar(
        select(ProjectDeletionJob)
        .where(ProjectDeletionJob.project_subject_id == project.id)
        .with_for_update()
    )
    if job is None:
        job = ProjectDeletionJob(
            id=uuid.uuid4(),
            project_subject_id=project.id,
            requested_by_user_id=actor_id,
            status="PENDING",
            storage_keys=storage_keys,
            attempts=0,
        )
        db.add(job)
    else:
        job.requested_by_user_id = actor_id
        job.status = "PENDING"
        job.storage_keys = storage_keys
        job.last_error_code = None
    db.commit()

    try:
        for storage_key in storage_keys:
            path = _storage_path(storage_key)
            path.unlink(missing_ok=True)
    except (OSError, ValueError):
        logger.warning("Project file deletion failed (project_id=%s)", project_id)
        failed_project = db.get(Project, project_id)
        failed_job = db.scalar(
            select(ProjectDeletionJob).where(
                ProjectDeletionJob.project_subject_id == project_id
            )
        )
        if failed_project is not None:
            failed_project.status = "DELETE_FAILED"
            failed_project.updated_at = utcnow()
        if failed_job is not None:
            failed_job.status = "FAILED"
            failed_job.attempts += 1
            failed_job.last_error_code = "FILE_DELETE_FAILED"
            failed_job.updated_at = utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail="project deletion failed") from None

    deleted_project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    finished_job = db.scalar(
        select(ProjectDeletionJob)
        .where(ProjectDeletionJob.project_subject_id == project_id)
        .with_for_update()
    )
    if deleted_project is not None:
        db.delete(deleted_project)
    now = utcnow()
    # Previous project audit events intentionally carry no payload, but only a
    # single minimal tombstone is retained after hard deletion.
    db.execute(delete(AuditEntry).where(AuditEntry.project_subject_id == project_id))
    _audit(
        db,
        "PROJECT_DELETED",
        actor_id=actor_id,
        project_id=project_id,
        aggregate={
            "scenario_count": scenario_count,
            "run_count": run_count,
            "file_count": len(files),
        },
        retention_until=now + timedelta(days=retention_days),
    )
    if finished_job is not None:
        db.delete(finished_job)
    db.commit()


def purge_expired_tombstones(db: Session, *, now: datetime | None = None) -> int:
    now = now or utcnow()
    result = db.execute(
        delete(AuditEntry).where(
            AuditEntry.event_type == "PROJECT_DELETED",
            AuditEntry.retention_until.is_not(None),
            AuditEntry.retention_until <= now,
        )
    )
    db.commit()
    return result.rowcount or 0


def _require_admin_csrf(context: AuthContext = Depends(require_csrf)) -> AuthContext:
    if context.user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="administrator role required")
    return context


def create_persistence_router(
    calculate: Callable[[UserInput], CalculationResponse],
    *,
    resolve_catalog: Callable[[], Any] | None = None,
    calculate_for_catalog: Callable[[UserInput, Any], CalculationResponse] | None = None,
    readiness_for_catalog: Callable[..., Any] | None = None,
    resolve_object_profile_version: Callable[[], str] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/auth/register", status_code=status.HTTP_201_CREATED)
    def register(
        payload: RegisterRequest,
        response: Response,
        db: Session = Depends(database_session),
    ):
        user = User(
            id=uuid.uuid4(),
            email_normalized=payload.email,
            password_hash=hash_password(payload.password),
            name=payload.name,
            role="USER",
            status="ACTIVE",
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="account already exists") from None
        _, token, csrf = create_session(db, user)
        _audit(db, "USER_REGISTERED", actor_id=user.id, subject_user_id=user.id)
        db.commit()
        set_session_cookies(response, token, csrf)
        return {"user": _user_dict(user), "csrf_token": csrf}

    @router.post("/auth/login")
    def login(
        payload: Credentials,
        response: Response,
        db: Session = Depends(database_session),
    ):
        user = db.scalar(select(User).where(User.email_normalized == payload.email))
        password_valid = verify_password(
            user.password_hash if user is not None else None,
            payload.password,
        )
        if (
            user is None
            or user.status != "ACTIVE"
            or not password_valid
        ):
            raise HTTPException(status_code=401, detail="invalid credentials")
        user.last_login_at = utcnow()
        _, token, csrf = create_session(db, user)
        _audit(db, "USER_LOGGED_IN", actor_id=user.id, subject_user_id=user.id)
        db.commit()
        set_session_cookies(response, token, csrf)
        return {"user": _user_dict(user), "csrf_token": csrf}

    @router.get("/auth/me")
    def me(context: AuthContext = Depends(require_auth_context)):
        return {"user": _user_dict(context.user)}

    @router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(
        response: Response,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        context.session.revoked_at = utcnow()
        db.commit()
        clear_session_cookies(response)

    @router.get("/admin/users")
    def list_users(
        _context: AuthContext = Depends(require_admin),
        db: Session = Depends(database_session),
    ):
        users = db.scalars(select(User).order_by(User.created_at, User.id)).all()
        return {"items": [_user_dict(user) for user in users]}

    @router.post("/admin/users", status_code=status.HTTP_201_CREATED)
    def create_user(
        payload: AdminCreateUserRequest,
        context: AuthContext = Depends(_require_admin_csrf),
        db: Session = Depends(database_session),
    ):
        user = User(
            id=uuid.uuid4(),
            email_normalized=payload.email,
            password_hash=hash_password(payload.password),
            name=payload.name,
            role=payload.role,
            status="ACTIVE",
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="account already exists") from None
        _audit(
            db,
            "USER_CREATED_BY_ADMIN",
            actor_id=context.user.id,
            subject_user_id=user.id,
            aggregate={"role": user.role},
        )
        db.commit()
        return _user_dict(user)

    @router.patch("/admin/users/{user_id}")
    def update_user(
        user_id: uuid.UUID,
        payload: AdminUpdateUserRequest,
        context: AuthContext = Depends(_require_admin_csrf),
        db: Session = Depends(database_session),
    ):
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes:
            user.name = changes["name"]
        if "role" in changes:
            user.role = changes["role"]
        if "status" in changes:
            user.status = changes["status"]
        user.updated_at = utcnow()
        if user.status == "DISABLED":
            db.execute(
                delete(UserSession).where(UserSession.user_id == user.id)
            )
        _audit(
            db,
            "USER_UPDATED_BY_ADMIN",
            actor_id=context.user.id,
            subject_user_id=user.id,
            aggregate={"fields": sorted(changes)},
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409, detail="last active administrator cannot be changed"
            ) from None
        return _user_dict(user)

    @router.post("/admin/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
    def reset_password(
        user_id: uuid.UUID,
        payload: PasswordResetRequest,
        context: AuthContext = Depends(_require_admin_csrf),
        db: Session = Depends(database_session),
    ):
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        user.password_hash = hash_password(payload.password)
        user.updated_at = utcnow()
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        _audit(
            db,
            "USER_PASSWORD_RESET",
            actor_id=context.user.id,
            subject_user_id=user.id,
        )
        db.commit()

    @router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_user(
        user_id: uuid.UUID,
        context: AuthContext = Depends(_require_admin_csrf),
        db: Session = Depends(database_session),
    ):
        if user_id == context.user.id:
            raise HTTPException(status_code=409, detail="cannot delete current account")
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        if user.role == "ADMIN" and user.status == "ACTIVE":
            active_admins = db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == "ADMIN", User.status == "ACTIVE")
            ) or 0
            if active_admins <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="last active administrator cannot be deleted",
                )
        project_ids = list(
            db.scalars(select(Project.id).where(Project.owner_id == user.id)).all()
        )
        for project_id in project_ids:
            delete_project(db, project_id, user.id, context.user.id)
        user = db.get(User, user_id)
        if user is None:
            return
        _audit(
            db,
            "USER_DELETED_BY_ADMIN",
            actor_id=context.user.id,
            subject_user_id=user.id,
            aggregate={"project_count": len(project_ids)},
        )
        db.delete(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409, detail="last active administrator cannot be deleted"
            ) from None

    @router.get("/projects")
    def list_projects(
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        projects = db.scalars(
            select(Project)
            .where(Project.owner_id == context.user.id, Project.status == "ACTIVE")
            .order_by(Project.updated_at.desc(), Project.id)
        ).all()
        return {"items": [_project_dict(db, project) for project in projects]}

    @router.post("/projects", status_code=status.HTTP_201_CREATED)
    def create_project(
        payload: ProjectCreateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        project = Project(
            id=uuid.uuid4(),
            owner_id=context.user.id,
            name=payload.name,
            description=payload.description,
            profile=payload.profile,
            status="ACTIVE",
        )
        db.add(project)
        for slot, name in SCENARIO_SLOTS:
            db.add(
                Scenario(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    slot=slot,
                    name=name,
                    inputs={},
                )
            )
        _audit(db, "PROJECT_CREATED", actor_id=context.user.id, project_id=project.id)
        db.commit()
        return _project_dict(db, project)

    @router.get("/projects/{project_id}")
    def get_project(
        project_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        return _project_dict(db, _owned_project(db, project_id, context.user.id))

    @router.get("/project-file-templates/{profile_code}.csv")
    def download_project_file_template(profile_code: str):
        try:
            filename, payload = build_csv_template(profile_code)
        except IntakeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return Response(
            content=payload,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/projects/{project_id}/files/preview")
    async def preview_project_file(
        project_id: uuid.UUID,
        profile_code: str = Form(...),
        file: UploadFile = File(...),
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        _owned_project(db, project_id, context.user.id)
        payload = await _read_project_upload(file)
        return _inspect_upload(file.filename, payload, profile_code).public_dict()

    @router.post(
        "/projects/{project_id}/files/apply", status_code=status.HTTP_201_CREATED
    )
    async def apply_project_file(
        project_id: uuid.UUID,
        scenario_id: uuid.UUID = Form(...),
        profile_code: str = Form(...),
        file: UploadFile = File(...),
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        project = _owned_project(db, project_id, context.user.id)
        scenario = db.scalar(
            select(Scenario)
            .where(Scenario.id == scenario_id, Scenario.project_id == project.id)
            .with_for_update()
        )
        if scenario is None:
            raise HTTPException(status_code=404, detail="scenario not found")
        payload = await _read_project_upload(file)
        result = _inspect_upload(file.filename, payload, profile_code)
        if not result.valid:
            raise HTTPException(
                status_code=422,
                detail={"code": "FILE_VALIDATION_FAILED", "report": result.report},
            )

        file_id = uuid.uuid4()
        suffix = ".xlsx" if result.file_format == "XLSX" else ".csv"
        storage_key = f"{project.id}/{file_id}/{result.sha256}{suffix}"
        path = _storage_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=False)
        try:
            path.write_bytes(payload)
            project_file = ProjectFile(
                id=file_id,
                project_id=project.id,
                original_name=result.original_name,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if result.file_format == "XLSX"
                    else "text/csv"
                ),
                byte_size=result.byte_size,
                sha256=result.sha256,
                storage_key=storage_key,
            )
            imported = ProjectFileImport(
                id=uuid.uuid4(),
                project_file_id=file_id,
                scenario_id=scenario.id,
                profile_code=result.profile_code,
                file_format=result.file_format,
                profile_version=result.profile_version,
                parameter_values=result.parameter_values,
                parameter_provenance=result.parameter_provenance,
                normalized_input=result.normalized_input,
                provenance=result.provenance,
                validation_report=result.report,
            )
            db.add(project_file)
            db.add(imported)
            scenario.inputs = result.normalized_input or {}
            scenario.updated_at = utcnow()
            project.profile = {
                **project.profile,
                "object_profile_code": result.profile_code,
                "object_profile_version": result.profile_version,
                "input_provenance": result.provenance,
                "project_file_import_id": str(imported.id),
            }
            project.updated_at = utcnow()
            _audit(
                db,
                "PROJECT_FILE_APPLIED",
                actor_id=context.user.id,
                project_id=project.id,
                aggregate={
                    "file_id": str(file_id),
                    "scenario_id": str(scenario.id),
                    "profile_code": result.profile_code,
                    "sha256": result.sha256,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            try:
                path.parent.rmdir()
            except OSError:
                pass
            raise
        return _file_dict(db, project_file)

    @router.get("/projects/{project_id}/files")
    def list_project_files(
        project_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        _owned_project(db, project_id, context.user.id)
        items = db.scalars(
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at.desc(), ProjectFile.id)
        ).all()
        return {"items": [_file_dict(db, item) for item in items]}

    @router.get("/projects/{project_id}/files/{file_id}")
    def download_project_file(
        project_id: uuid.UUID,
        file_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        _owned_project(db, project_id, context.user.id)
        item = db.scalar(
            select(ProjectFile).where(
                ProjectFile.id == file_id, ProjectFile.project_id == project_id
            )
        )
        if item is None:
            raise HTTPException(status_code=404, detail="file not found")
        try:
            path = _storage_path(item.storage_key)
            payload = path.read_bytes()
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="file content unavailable") from None
        if hashlib.sha256(payload).hexdigest() != item.sha256:
            raise HTTPException(status_code=409, detail="file checksum mismatch")
        ascii_name = "project-input.xlsx" if item.original_name.lower().endswith(".xlsx") else "project-input.csv"
        return Response(
            content=payload,
            media_type=item.media_type,
            headers={"Content-Disposition": f'attachment; filename="{ascii_name}"'},
        )

    @router.patch("/projects/{project_id}")
    def update_project(
        project_id: uuid.UUID,
        payload: ProjectUpdateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        project = _owned_project(db, project_id, context.user.id)
        changes = payload.model_dump(exclude_unset=True)
        for field in ("name", "description", "profile"):
            if field in changes:
                setattr(project, field, changes[field])
        project.updated_at = utcnow()
        _audit(
            db,
            "PROJECT_UPDATED",
            actor_id=context.user.id,
            project_id=project.id,
            aggregate={"fields": sorted(changes)},
        )
        db.commit()
        return _project_dict(db, project)

    @router.post("/projects/{project_id}/copy", status_code=status.HTTP_201_CREATED)
    def copy_project(
        project_id: uuid.UUID,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        source = _owned_project(db, project_id, context.user.id)
        source_scenarios = db.scalars(
            select(Scenario).where(Scenario.project_id == source.id)
        ).all()
        copy = Project(
            id=uuid.uuid4(),
            owner_id=context.user.id,
            copied_from_project_id=source.id,
            name=f"{source.name} — копия"[:200],
            description=source.description,
            profile=json.loads(json.dumps(source.profile)),
            status="ACTIVE",
        )
        db.add(copy)
        for scenario in source_scenarios:
            db.add(
                Scenario(
                    id=uuid.uuid4(),
                    project_id=copy.id,
                    slot=scenario.slot,
                    name=scenario.name,
                    inputs=json.loads(json.dumps(scenario.inputs)),
                )
            )
        _audit(
            db,
            "PROJECT_COPIED",
            actor_id=context.user.id,
            project_id=copy.id,
        )
        db.commit()
        return _project_dict(db, copy)

    @router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_project(
        project_id: uuid.UUID,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        delete_project(db, project_id, context.user.id, context.user.id)

    @router.patch("/projects/{project_id}/scenarios/{scenario_id}")
    def update_scenario(
        project_id: uuid.UUID,
        scenario_id: uuid.UUID,
        payload: ScenarioUpdateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        _owned_project(db, project_id, context.user.id)
        scenario = db.scalar(
            select(Scenario).where(
                Scenario.id == scenario_id, Scenario.project_id == project_id
            )
        )
        if scenario is None:
            raise HTTPException(status_code=404, detail="scenario not found")
        changes = payload.model_dump(exclude_unset=True)
        for field in ("name", "inputs"):
            if field in changes:
                setattr(scenario, field, changes[field])
        scenario.updated_at = utcnow()
        _audit(
            db,
            "SCENARIO_UPDATED",
            actor_id=context.user.id,
            project_id=project_id,
            aggregate={"slot": scenario.slot, "fields": sorted(changes)},
        )
        db.commit()
        return _scenario_dict(scenario)

    def execute_analysis(
        *,
        db: Session,
        project: Project,
        scenario: Scenario,
        input_model: UserInput,
        parent_run_id: uuid.UUID | None = None,
    ) -> AnalysisRun:
        input_snapshot = input_model.model_dump(mode="json")
        if resolve_catalog is None:
            raise RuntimeError("catalog resolver is required for persisted analysis")
        catalog_snapshot = resolve_catalog()
        catalog_version = catalog_snapshot.version
        catalog_version_code = catalog_version.code
        catalog_version_id = uuid.UUID(catalog_version.id)
        object_profile_version = (
            resolve_object_profile_version()
            if resolve_object_profile_version is not None
            else OBJECT_PROFILE_VERSION
        )
        run = AnalysisRun(
            id=uuid.uuid4(),
            project_id=project.id,
            scenario_id=scenario.id,
            parent_run_id=parent_run_id,
            status="PENDING",
            input_snapshot=input_snapshot,
            input_sha256=_canonical_sha256(input_snapshot),
            catalog_version_id=catalog_version_id,
            catalog_version_code=catalog_version_code,
            rules_version=RULES_VERSION,
            economics_version=ECONOMICS_VERSION,
            object_profile_version=object_profile_version,
            application_version=APPLICATION_VERSION,
            diagnostics={},
        )
        db.add(run)
        db.commit()
        run.status = "RUNNING"
        run.started_at = utcnow()
        db.commit()
        try:
            calculation = (
                calculate_for_catalog(input_model, catalog_snapshot)
                if catalog_snapshot is not None and calculate_for_catalog is not None
                else calculate(input_model)
            )
        except HTTPException as exc:
            run.status = "FAILED"
            run.finished_at = utcnow()
            run.diagnostics = {
                "error_code": "CALCULATION_REJECTED" if exc.status_code < 500 else "CALCULATION_ERROR"
            }
            db.commit()
            raise
        except Exception:
            logger.exception("Persisted calculation failed (run_id=%s)", run.id)
            run.status = "FAILED"
            run.finished_at = utcnow()
            run.diagnostics = {"error_code": "CALCULATION_ERROR"}
            db.commit()
            raise HTTPException(status_code=500, detail="calculation failed") from None

        result_snapshot = calculation.model_dump(mode="json")
        if readiness_for_catalog is not None:
            imported = db.scalar(
                select(ProjectFileImport)
                .where(ProjectFileImport.scenario_id == scenario.id)
                .order_by(ProjectFileImport.applied_at.desc())
                .limit(1)
            )
            use_import = (
                imported is not None
                and UserInput.model_validate(imported.normalized_input).model_dump(
                    mode="json"
                )
                == input_snapshot
            )
            readiness = readiness_for_catalog(
                input_model,
                catalog_snapshot,
                provenance=imported.provenance if use_import else {},
                parameter_values=imported.parameter_values if use_import else {},
                parameter_provenance=(
                    imported.parameter_provenance if use_import else {}
                ),
            )
            result_snapshot["readiness_report"] = (
                readiness.model_dump(mode="json")
                if hasattr(readiness, "model_dump")
                else readiness
            )
        scenario_spec = result_snapshot.get("scenario_spec")
        if not isinstance(scenario_spec, dict):
            run.status = "FAILED"
            run.finished_at = utcnow()
            run.diagnostics = {"error_code": "SCENARIO_SPEC_MISSING"}
            db.commit()
            raise HTTPException(status_code=500, detail="scenario snapshot unavailable")
        run.status = "SUCCEEDED"
        run.result_snapshot = result_snapshot
        run.result_sha256 = _canonical_sha256(result_snapshot)
        run.scenario_spec_snapshot = scenario_spec
        run.scenario_spec_sha256 = _canonical_sha256(scenario_spec)
        run.revision_id = calculation.revision_id
        run.finished_at = utcnow()
        db.commit()
        return run

    @router.post(
        "/projects/{project_id}/analysis-runs",
        status_code=status.HTTP_201_CREATED,
    )
    def create_analysis_run(
        project_id: uuid.UUID,
        payload: AnalysisCreateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        project = _owned_project(db, project_id, context.user.id)
        scenario = db.scalar(
            select(Scenario).where(
                Scenario.id == payload.scenario_id, Scenario.project_id == project.id
            )
        )
        if scenario is None:
            raise HTTPException(status_code=404, detail="scenario not found")
        run = execute_analysis(
            db=db, project=project, scenario=scenario, input_model=payload.input
        )
        _audit(
            db,
            "ANALYSIS_RUN_SUCCEEDED",
            actor_id=context.user.id,
            project_id=project.id,
            aggregate={"run_id": str(run.id)},
        )
        db.commit()
        return _run_dict(run, include_snapshots=True)

    @router.get("/projects/{project_id}/analysis-runs")
    def list_analysis_runs(
        project_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        _owned_project(db, project_id, context.user.id)
        runs = db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.project_id == project_id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id)
        ).all()
        return {"items": [_run_dict(run, include_snapshots=False) for run in runs]}

    @router.get("/projects/{project_id}/analysis-runs/{run_id}")
    def get_analysis_run(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        _owned_project(db, project_id, context.user.id)
        run = db.scalar(
            select(AnalysisRun).where(
                AnalysisRun.id == run_id, AnalysisRun.project_id == project_id
            )
        )
        if run is None:
            raise HTTPException(status_code=404, detail="analysis run not found")
        return _run_dict(run, include_snapshots=True)

    @router.post(
        "/projects/{project_id}/analysis-runs/{run_id}/rerun",
        status_code=status.HTTP_201_CREATED,
    )
    def rerun_analysis(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ):
        project = _owned_project(db, project_id, context.user.id)
        source = db.scalar(
            select(AnalysisRun).where(
                AnalysisRun.id == run_id, AnalysisRun.project_id == project_id
            )
        )
        if source is None:
            raise HTTPException(status_code=404, detail="analysis run not found")
        scenario = db.get(Scenario, source.scenario_id) if source.scenario_id else None
        if scenario is None or scenario.project_id != project.id:
            raise HTTPException(status_code=409, detail="source scenario is unavailable")
        input_model = UserInput.model_validate(source.input_snapshot)
        run = execute_analysis(
            db=db,
            project=project,
            scenario=scenario,
            input_model=input_model,
            parent_run_id=source.id,
        )
        _audit(
            db,
            "ANALYSIS_RUN_RERUN",
            actor_id=context.user.id,
            project_id=project.id,
            aggregate={"run_id": str(run.id), "parent_run_id": str(source.id)},
        )
        db.commit()
        return _run_dict(run, include_snapshots=True)

    return router
