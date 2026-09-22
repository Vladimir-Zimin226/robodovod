"""Persistence mappings for users, projects, scenarios and immutable runs.

Alembic owns the DDL.  Security and lifecycle rules that cannot be expressed by
SQLAlchemy metadata are installed by migration 0003.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from storage_models import Base, SHA256_CHECK


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        CheckConstraint(
            "email_normalized = lower(btrim(email_normalized)) "
            "AND length(email_normalized) BETWEEN 3 AND 320 "
            "AND position('@' in email_normalized) > 1",
            name="ck_users_email_normalized",
        ),
        CheckConstraint("length(password_hash) > 0", name="ck_users_password_hash"),
        CheckConstraint(
            "name IS NULL OR (name = btrim(name) AND length(name) BETWEEN 1 AND 200)",
            name="ck_users_name",
        ),
        CheckConstraint("role IN ('USER', 'ADMIN')", name="ck_users_role"),
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_users_status"),
        CheckConstraint("updated_at >= created_at", name="ck_users_timestamp_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="USER", server_default=text("'USER'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="ACTIVE", server_default=text("'ACTIVE'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_sha256", name="uq_user_sessions_token_sha256"),
        CheckConstraint(
            f"token_sha256 ~ '{SHA256_CHECK}'", name="ck_user_sessions_token_sha256"
        ),
        CheckConstraint(
            f"csrf_sha256 ~ '{SHA256_CHECK}'", name="ck_user_sessions_csrf_sha256"
        ),
        CheckConstraint("expires_at > created_at", name="ck_user_sessions_expiry"),
        Index("ix_user_sessions_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    csrf_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "name = btrim(name) AND length(name) BETWEEN 1 AND 200",
            name="ck_projects_name",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 4000",
            name="ck_projects_description",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DELETING', 'DELETE_FAILED')",
            name="ck_projects_status",
        ),
        CheckConstraint("jsonb_typeof(profile) = 'object'", name="ck_projects_profile_object"),
        CheckConstraint("updated_at >= created_at", name="ck_projects_timestamp_order"),
        Index("ix_projects_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    copied_from_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="ACTIVE", server_default=text("'ACTIVE'")
    )
    profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectFile(Base):
    __tablename__ = "project_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_project_files_storage_key"),
        CheckConstraint("length(btrim(original_name)) > 0", name="ck_project_files_name"),
        CheckConstraint("length(btrim(media_type)) > 0", name="ck_project_files_media_type"),
        CheckConstraint("byte_size > 0", name="ck_project_files_byte_size"),
        CheckConstraint(
            f"sha256 ~ '{SHA256_CHECK}'", name="ck_project_files_sha256"
        ),
        CheckConstraint(
            "storage_key = btrim(storage_key) AND length(storage_key) > 0",
            name="ck_project_files_storage_key",
        ),
        Index("ix_project_files_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectFileImport(Base):
    __tablename__ = "project_file_imports"
    __table_args__ = (
        UniqueConstraint("project_file_id", name="uq_project_file_imports_file"),
        CheckConstraint(
            "profile_code IN ('warehouse', 'airport', 'medical_facility')",
            name="ck_project_file_imports_profile",
        ),
        CheckConstraint(
            "file_format IN ('XLSX', 'CSV')", name="ck_project_file_imports_format"
        ),
        CheckConstraint(
            "length(btrim(profile_version)) > 0",
            name="ck_project_file_imports_profile_version",
        ),
        CheckConstraint(
            "jsonb_typeof(normalized_input) = 'object'",
            name="ck_project_file_imports_input_object",
        ),
        CheckConstraint(
            "jsonb_typeof(parameter_values) = 'object'",
            name="ck_project_file_imports_values_object",
        ),
        CheckConstraint(
            "jsonb_typeof(parameter_provenance) = 'object'",
            name="ck_project_file_imports_parameter_provenance_object",
        ),
        CheckConstraint(
            "jsonb_typeof(provenance) = 'object'",
            name="ck_project_file_imports_provenance_object",
        ),
        CheckConstraint(
            "jsonb_typeof(validation_report) = 'object'",
            name="ck_project_file_imports_report_object",
        ),
        Index("ix_project_file_imports_scenario", "scenario_id", "applied_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    profile_code: Mapped[str] = mapped_column(Text, nullable=False)
    file_format: Mapped[str] = mapped_column(Text, nullable=False)
    profile_version: Mapped[str] = mapped_column(Text, nullable=False)
    parameter_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parameter_provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        UniqueConstraint("project_id", "slot", name="uq_scenarios_project_slot"),
        CheckConstraint(
            "slot IN ('BASE', 'OPTIMISTIC', 'PESSIMISTIC')", name="ck_scenarios_slot"
        ),
        CheckConstraint(
            "name = btrim(name) AND length(name) BETWEEN 1 AND 120",
            name="ck_scenarios_name",
        ),
        CheckConstraint("jsonb_typeof(inputs) = 'object'", name="ck_scenarios_inputs_object"),
        CheckConstraint("updated_at >= created_at", name="ck_scenarios_timestamp_order"),
        Index("ix_scenarios_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "run_kind IN ('FULL_ANALYSIS', 'CAPACITY_ANALYSIS')",
            name="ck_analysis_runs_kind",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="ck_analysis_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(input_snapshot) = 'object'", name="ck_analysis_runs_input_object"
        ),
        CheckConstraint(
            "result_snapshot IS NULL OR jsonb_typeof(result_snapshot) = 'object'",
            name="ck_analysis_runs_result_object",
        ),
        CheckConstraint(
            "scenario_spec_snapshot IS NULL OR jsonb_typeof(scenario_spec_snapshot) = 'object'",
            name="ck_analysis_runs_scenario_spec_object",
        ),
        CheckConstraint(
            "jsonb_typeof(diagnostics) = 'object'", name="ck_analysis_runs_diagnostics_object"
        ),
        CheckConstraint(
            f"input_sha256 ~ '{SHA256_CHECK}'", name="ck_analysis_runs_input_sha256"
        ),
        CheckConstraint(
            f"result_sha256 IS NULL OR result_sha256 ~ '{SHA256_CHECK}'",
            name="ck_analysis_runs_result_sha256",
        ),
        CheckConstraint(
            f"scenario_spec_sha256 IS NULL OR scenario_spec_sha256 ~ '{SHA256_CHECK}'",
            name="ck_analysis_runs_scenario_spec_sha256",
        ),
        CheckConstraint(
            "trace_snapshot IS NULL OR jsonb_typeof(trace_snapshot) = 'object'",
            name="ck_analysis_runs_trace_object",
        ),
        CheckConstraint(
            "version_bindings_snapshot IS NULL OR jsonb_typeof(version_bindings_snapshot) = 'object'",
            name="ck_analysis_runs_version_bindings_object",
        ),
        CheckConstraint(
            f"trace_sha256 IS NULL OR trace_sha256 ~ '{SHA256_CHECK}'",
            name="ck_analysis_runs_trace_sha256",
        ),
        CheckConstraint(
            f"version_bindings_sha256 IS NULL OR version_bindings_sha256 ~ '{SHA256_CHECK}'",
            name="ck_analysis_runs_version_bindings_sha256",
        ),
        CheckConstraint(
            "length(btrim(catalog_version_code)) > 0 "
            "AND length(btrim(rules_version)) > 0 "
            "AND (economics_version IS NULL OR length(btrim(economics_version)) > 0) "
            "AND length(btrim(object_profile_version)) > 0 "
            "AND length(btrim(application_version)) > 0 "
            "AND ((run_kind = 'FULL_ANALYSIS' AND economics_version IS NOT NULL) "
            "OR (run_kind = 'CAPACITY_ANALYSIS' AND economics_version IS NULL "
            "AND version_bindings_snapshot IS NOT NULL AND version_bindings_sha256 IS NOT NULL))",
            name="ck_analysis_runs_versions_nonempty",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL "
            "AND result_snapshot IS NULL AND scenario_spec_snapshot IS NULL AND trace_snapshot IS NULL) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND result_snapshot IS NULL AND scenario_spec_snapshot IS NULL AND trace_snapshot IS NULL) OR "
            "(status = 'SUCCEEDED' AND run_kind = 'FULL_ANALYSIS' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND result_snapshot IS NOT NULL AND result_sha256 IS NOT NULL "
            "AND scenario_spec_snapshot IS NOT NULL AND scenario_spec_sha256 IS NOT NULL "
            "AND trace_snapshot IS NULL AND trace_sha256 IS NULL) OR "
            "(status = 'SUCCEEDED' AND run_kind = 'CAPACITY_ANALYSIS' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND result_snapshot IS NOT NULL AND result_sha256 IS NOT NULL "
            "AND scenario_spec_snapshot IS NULL AND scenario_spec_sha256 IS NULL "
            "AND trace_snapshot IS NOT NULL AND trace_sha256 IS NOT NULL "
            "AND version_bindings_snapshot IS NOT NULL AND version_bindings_sha256 IS NOT NULL) OR "
            "(status IN ('FAILED', 'CANCELLED') AND started_at IS NOT NULL "
            "AND finished_at IS NOT NULL AND result_snapshot IS NULL "
            "AND result_sha256 IS NULL AND scenario_spec_snapshot IS NULL "
            "AND scenario_spec_sha256 IS NULL AND trace_snapshot IS NULL AND trace_sha256 IS NULL)",
            name="ck_analysis_runs_state_payload",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_analysis_runs_timestamp_order",
        ),
        Index("ix_analysis_runs_project_created", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    run_kind: Mapped[str] = mapped_column(
        Text, nullable=False, default="FULL_ANALYSIS"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="PENDING", server_default=text("'PENDING'")
    )
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result_sha256: Mapped[str | None] = mapped_column(Text)
    scenario_spec_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scenario_spec_sha256: Mapped[str | None] = mapped_column(Text)
    trace_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    trace_sha256: Mapped[str | None] = mapped_column(Text)
    version_bindings_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    version_bindings_sha256: Mapped[str | None] = mapped_column(Text)
    revision_id: Mapped[str | None] = mapped_column(Text)
    catalog_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_versions.id", ondelete="RESTRICT")
    )
    catalog_version_code: Mapped[str] = mapped_column(Text, nullable=False)
    rules_version: Mapped[str] = mapped_column(Text, nullable=False)
    economics_version: Mapped[str | None] = mapped_column(Text)
    object_profile_version: Mapped[str] = mapped_column(Text, nullable=False)
    application_version: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEntry(Base):
    __tablename__ = "audit_entries"
    __table_args__ = (
        CheckConstraint(
            "event_type = btrim(event_type) AND length(event_type) BETWEEN 1 AND 100",
            name="ck_audit_entries_event_type",
        ),
        CheckConstraint("jsonb_typeof(aggregate) = 'object'", name="ck_audit_entries_aggregate"),
        CheckConstraint(
            "retention_until IS NULL OR retention_until >= created_at",
            name="ck_audit_entries_retention",
        ),
        Index("ix_audit_entries_retention", "retention_until"),
        Index("ix_audit_entries_project", "project_subject_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    project_subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    aggregate: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectDeletionJob(Base):
    __tablename__ = "project_deletion_jobs"
    __table_args__ = (
        UniqueConstraint("project_subject_id", name="uq_project_deletion_jobs_project"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'FAILED', 'SUCCEEDED')",
            name="ck_project_deletion_jobs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(storage_keys) = 'array'", name="ck_project_deletion_jobs_keys"
        ),
        CheckConstraint("attempts >= 0", name="ck_project_deletion_jobs_attempts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    storage_keys: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
