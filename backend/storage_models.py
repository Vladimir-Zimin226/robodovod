"""SQLAlchemy mappings for migration 0001 storage control-plane tables.

Alembic owns production DDL. PostgreSQL lifecycle and immutability triggers are
defined explicitly in the migration because SQLAlchemy metadata cannot model
constraint triggers.
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
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


SHA256_CHECK = "^[0-9a-f]{64}$"


class Base(DeclarativeBase):
    pass


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_catalog_versions_code"),
        CheckConstraint(
            "length(btrim(code)) > 0 AND code = btrim(code)",
            name="ck_catalog_versions_code_nonempty",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'VALIDATED', 'PUBLISHED', 'RETIRED')",
            name="ck_catalog_versions_status",
        ),
        CheckConstraint(
            "length(btrim(schema_version)) > 0 AND schema_version = btrim(schema_version)",
            name="ck_catalog_versions_schema_version_nonempty",
        ),
        CheckConstraint(
            f"content_sha256 IS NULL OR content_sha256 ~ '{SHA256_CHECK}'",
            name="ck_catalog_versions_content_sha256",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_catalog_versions_updated_after_created",
        ),
        CheckConstraint(
            "(status = 'DRAFT' AND validated_at IS NULL AND published_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'VALIDATED' AND validated_at IS NOT NULL AND published_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'PUBLISHED' AND validated_at IS NOT NULL AND published_at IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'RETIRED' AND validated_at IS NOT NULL AND published_at IS NOT NULL AND retired_at IS NOT NULL)",
            name="ck_catalog_versions_lifecycle_presence",
        ),
        CheckConstraint(
            "(validated_at IS NULL OR validated_at >= created_at) AND "
            "(published_at IS NULL OR published_at >= validated_at) AND "
            "(retired_at IS NULL OR retired_at >= published_at)",
            name="ck_catalog_versions_lifecycle_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="DRAFT", server_default=text("'DRAFT'")
    )
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceArtifact(Base):
    __tablename__ = "source_artifacts"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_source_artifacts_sha256"),
        CheckConstraint(
            f"sha256 ~ '{SHA256_CHECK}'", name="ck_source_artifacts_sha256"
        ),
        CheckConstraint(
            "length(btrim(original_name)) > 0",
            name="ck_source_artifacts_original_name_nonempty",
        ),
        CheckConstraint(
            "length(btrim(media_type)) > 0",
            name="ck_source_artifacts_media_type_nonempty",
        ),
        CheckConstraint("byte_size > 0", name="ck_source_artifacts_byte_size_positive"),
        CheckConstraint(
            "storage_key IS NULL OR length(btrim(storage_key)) > 0",
            name="ck_source_artifacts_storage_key_nonempty",
        ),
        CheckConstraint(
            "provenance_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="ck_source_artifacts_provenance_status",
        ),
        CheckConstraint(
            "license_status IN ('UNKNOWN', 'PERMITTED', 'RESTRICTED')",
            name="ck_source_artifacts_license_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text)
    provenance_status: Mapped[str] = mapped_column(Text, nullable=False)
    license_status: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogVersionSource(Base):
    __tablename__ = "catalog_version_sources"
    __table_args__ = (
        PrimaryKeyConstraint(
            "catalog_version_id",
            "source_artifact_id",
            name="pk_catalog_version_sources",
        ),
        UniqueConstraint(
            "catalog_version_id",
            "role",
            "ordinal",
            name="uq_catalog_version_sources_role_ordinal",
        ),
        CheckConstraint(
            "role IN ('BASE', 'ENRICHMENT', 'REFERENCE', 'IMPORT_BUNDLE')",
            name="ck_catalog_version_sources_role",
        ),
        CheckConstraint("ordinal >= 0", name="ck_catalog_version_sources_ordinal"),
    )

    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class ImportRun(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        UniqueConstraint("request_key", name="uq_import_runs_request_key"),
        CheckConstraint(
            "phase IN ('BASE', 'ENRICHMENT')", name="ck_import_runs_phase"
        ),
        CheckConstraint(
            "mode IN ('VALIDATE_ONLY', 'COMMIT')", name="ck_import_runs_mode"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_import_runs_status",
        ),
        CheckConstraint(
            f"bundle_sha256 ~ '{SHA256_CHECK}'", name="ck_import_runs_bundle_sha256"
        ),
        CheckConstraint(
            "request_key IS NULL OR length(btrim(request_key)) > 0",
            name="ck_import_runs_request_key_nonempty",
        ),
        CheckConstraint(
            "jsonb_typeof(counts) = 'object'", name="ck_import_runs_counts_object"
        ),
        CheckConstraint(
            "jsonb_typeof(diagnostics) = 'object'",
            name="ck_import_runs_diagnostics_object",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
            "(status IN ('SUCCEEDED', 'FAILED') AND started_at IS NOT NULL AND finished_at IS NOT NULL)",
            name="ck_import_runs_status_timestamps",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_import_runs_finished_after_started",
        ),
        Index(
            "uq_import_runs_successful_commit",
            "catalog_version_id",
            "phase",
            "bundle_sha256",
            unique=True,
            postgresql_where=text("status = 'SUCCEEDED' AND mode = 'COMMIT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    bundle_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    request_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    diagnostics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CatalogActivation(Base):
    __tablename__ = "catalog_activations"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(slot)) > 0 AND slot = btrim(slot)",
            name="ck_catalog_activations_slot_nonempty",
        ),
        CheckConstraint(
            "actor_subject IS NULL OR length(btrim(actor_subject)) > 0",
            name="ck_catalog_activations_actor_subject_nonempty",
        ),
        CheckConstraint(
            "deactivated_at IS NULL OR deactivated_at >= activated_at",
            name="ck_catalog_activations_timestamp_order",
        ),
        Index(
            "uq_catalog_activations_active_slot",
            "slot",
            unique=True,
            postgresql_where=text("deactivated_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_subject: Mapped[str | None] = mapped_column(Text)
