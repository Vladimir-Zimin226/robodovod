"""SQLAlchemy mappings for migration 0002 catalog domain schema.

The current runtime does not query these mappings yet. Alembic remains the only
production DDL mechanism; mappings exist to define the future repository
boundary and to detect drift from migrations.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from storage_models import Base

EVIDENCE_STATUSES = (
    "NORMALIZED_FROM_ORGANIZER",
    "ORGANIZER_CSV",
    "ORGANIZER_CSV_CORROBORATING",
    "ORGANIZER_ASSUMPTION",
    "CORROBORATED",
    "CROSS_DOCUMENT_CORROBORATING",
    "CROSS_DOCUMENT_ENRICHED",
    "ORGANIZER_NAME",
    "VERIFIED_OFFICIAL",
    "VERIFIED_AUTHORIZED_PARTNER",
    "MANUALLY_APPROVED",
    "CONFLICT",
    "AMBIGUOUS_MODEL_MATCH",
    "NOT_FOUND",
    "UNKNOWN",
)
RESOLUTION_STATUSES = (
    "CORROBORATED",
    "CROSS_DOCUMENT_ENRICHED",
    "ORGANIZER_NAME",
    "VERIFIED_OFFICIAL",
    "VERIFIED_AUTHORIZED_PARTNER",
    "MANUALLY_APPROVED",
    "CONFLICT",
    "AMBIGUOUS_MODEL_MATCH",
    "NOT_FOUND",
    "UNKNOWN",
)
SAFE_AUTOMATIC_STATUSES = (
    "CORROBORATED",
    "CROSS_DOCUMENT_ENRICHED",
    "ORGANIZER_NAME",
    "VERIFIED_OFFICIAL",
)
REVIEWED_STATUSES = ("VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Manufacturer(Base):
    __tablename__ = "manufacturers"
    __table_args__ = (
        UniqueConstraint(
            "catalog_version_id",
            "source_namespace",
            "source_record_key",
            name="uq_manufacturers_source_key",
        ),
        UniqueConstraint(
            "id", "catalog_version_id", name="uq_manufacturers_id_version"
        ),
        CheckConstraint(
            "length(btrim(source_namespace)) > 0 AND source_namespace = btrim(source_namespace)",
            name="ck_manufacturers_source_namespace_nonempty",
        ),
        CheckConstraint(
            "length(btrim(source_record_key)) > 0 AND source_record_key = btrim(source_record_key)",
            name="ck_manufacturers_source_record_key_nonempty",
        ),
        CheckConstraint(
            "length(btrim(name)) > 0", name="ck_manufacturers_name_nonempty"
        ),
        CheckConstraint(
            "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'",
            name="ck_manufacturers_country_code",
        ),
        CheckConstraint(
            "website_url IS NULL OR length(btrim(website_url)) > 0",
            name="ck_manufacturers_website_url_nonempty",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_manufacturers_catalog_version_id",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogSourceRow(Base):
    __tablename__ = "catalog_source_rows"
    __table_args__ = (
        UniqueConstraint(
            "source_artifact_id",
            "source_row_number",
            name="uq_catalog_source_rows_artifact_row",
        ),
        UniqueConstraint(
            "catalog_version_id",
            "source_namespace",
            "source_record_key",
            name="uq_catalog_source_rows_source_key",
        ),
        UniqueConstraint(
            "id", "catalog_version_id", name="uq_catalog_source_rows_id_version"
        ),
        CheckConstraint(
            "source_row_number > 0",
            name="ck_catalog_source_rows_row_number_positive",
        ),
        CheckConstraint(
            "length(btrim(source_namespace)) > 0 AND source_namespace = btrim(source_namespace)",
            name="ck_catalog_source_rows_source_namespace_nonempty",
        ),
        CheckConstraint(
            "length(btrim(source_record_key)) > 0 AND source_record_key = btrim(source_record_key)",
            name="ck_catalog_source_rows_source_record_key_nonempty",
        ),
        CheckConstraint(
            "jsonb_typeof(raw_payload) = 'object'",
            name="ck_catalog_source_rows_raw_payload_object",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id", "source_artifact_id"],
            [
                "catalog_version_sources.catalog_version_id",
                "catalog_version_sources.source_artifact_id",
            ],
            name="fk_catalog_source_rows_version_artifact",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_key: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EquipmentModel(Base):
    __tablename__ = "equipment_models"
    __table_args__ = (
        UniqueConstraint(
            "catalog_version_id",
            "organizer_id",
            name="uq_equipment_models_version_organizer_id",
        ),
        UniqueConstraint(
            "catalog_version_id",
            "source_namespace",
            "source_record_key",
            name="uq_equipment_models_source_key",
        ),
        UniqueConstraint(
            "id", "catalog_version_id", name="uq_equipment_models_id_version"
        ),
        CheckConstraint(
            "length(btrim(source_namespace)) > 0 AND source_namespace = btrim(source_namespace)",
            name="ck_equipment_models_source_namespace_nonempty",
        ),
        CheckConstraint(
            "length(btrim(source_record_key)) > 0 AND source_record_key = btrim(source_record_key)",
            name="ck_equipment_models_source_record_key_nonempty",
        ),
        CheckConstraint(
            "length(btrim(name)) > 0", name="ck_equipment_models_name_nonempty"
        ),
        CheckConstraint(
            "length(btrim(system_family)) > 0",
            name="ck_equipment_models_system_family_nonempty",
        ),
        CheckConstraint(
            "length(btrim(type_code)) > 0",
            name="ck_equipment_models_type_code_nonempty",
        ),
        CheckConstraint(
            "subtype_code IS NULL OR length(btrim(subtype_code)) > 0",
            name="ck_equipment_models_subtype_code_nonempty",
        ),
        CheckConstraint(
            "trl IS NULL OR trl BETWEEN 1 AND 9", name="ck_equipment_models_trl"
        ),
        CheckConstraint(
            "jsonb_typeof(attributes) = 'object'",
            name="ck_equipment_models_attributes_object",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_equipment_models_catalog_version_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["manufacturer_id", "catalog_version_id"],
            ["manufacturers.id", "manufacturers.catalog_version_id"],
            name="fk_equipment_models_manufacturer_version",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    manufacturer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    organizer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    system_family: Mapped[str] = mapped_column(Text, nullable=False)
    type_code: Mapped[str] = mapped_column(Text, nullable=False)
    subtype_code: Mapped[str | None] = mapped_column(Text)
    maturity_status: Mapped[str | None] = mapped_column(Text)
    trl: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogMediaAsset(Base):
    __tablename__ = "catalog_media_assets"
    __table_args__ = (
        UniqueConstraint(
            "id", "catalog_version_id", name="uq_catalog_media_assets_id_version"
        ),
        UniqueConstraint(
            "catalog_version_id",
            "sha256",
            name="uq_catalog_media_assets_version_sha256",
        ),
        UniqueConstraint("storage_key", name="uq_catalog_media_assets_storage_key"),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_media_assets_sha256"
        ),
        CheckConstraint(
            "media_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name="ck_catalog_media_assets_media_type",
        ),
        CheckConstraint("byte_size > 0", name="ck_catalog_media_assets_byte_size"),
        CheckConstraint(
            "width_px > 0 AND height_px > 0",
            name="ck_catalog_media_assets_dimensions",
        ),
        CheckConstraint(
            "storage_key = btrim(storage_key) AND length(storage_key) > 0",
            name="ck_catalog_media_assets_storage_key",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id", "source_artifact_id"],
            [
                "catalog_version_sources.catalog_version_id",
                "catalog_version_sources.source_artifact_id",
            ],
            name="fk_catalog_media_assets_version_artifact",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogPositionMedia(Base):
    __tablename__ = "catalog_position_media"
    __table_args__ = (
        UniqueConstraint(
            "catalog_source_row_id",
            "role",
            name="uq_catalog_position_media_source_row_role",
        ),
        UniqueConstraint(
            "catalog_version_id",
            "source_page",
            "source_slot",
            name="uq_catalog_position_media_source_locator",
        ),
        CheckConstraint("role IN ('PRIMARY')", name="ck_catalog_position_media_role"),
        CheckConstraint(
            "source_page > 0 AND source_slot > 0",
            name="ck_catalog_position_media_source_locator",
        ),
        ForeignKeyConstraint(
            ["catalog_source_row_id", "catalog_version_id"],
            ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"],
            name="fk_catalog_position_media_source_row_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["media_asset_id", "catalog_version_id"],
            ["catalog_media_assets.id", "catalog_media_assets.catalog_version_id"],
            name="fk_catalog_position_media_asset_version",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_catalog_position_media_version",
            "catalog_version_id",
            "catalog_source_row_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    catalog_source_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="PRIMARY", server_default=text("'PRIMARY'")
    )
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    source_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogDescriptionImport(Base):
    __tablename__ = "catalog_description_imports"
    __table_args__ = (
        UniqueConstraint(
            "catalog_version_id", name="uq_catalog_description_imports_version"
        ),
        CheckConstraint(
            "overlay_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_description_imports_overlay_sha256",
        ),
        CheckConstraint(
            "jsonb_typeof(report) = 'object'",
            name="ck_catalog_description_imports_report_object",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_catalog_description_imports_version",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    overlay_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogPositionEnrichment(Base):
    __tablename__ = "catalog_position_enrichments"
    __table_args__ = (
        UniqueConstraint(
            "catalog_source_row_id",
            name="uq_catalog_position_enrichments_source_row",
        ),
        UniqueConstraint(
            "catalog_version_id",
            "source_page",
            "source_slot",
            name="uq_catalog_position_enrichments_locator",
        ),
        CheckConstraint(
            "adapter IN ('page-oriented-v1', 'field-oriented-v1')",
            name="ck_catalog_position_enrichments_adapter",
        ),
        CheckConstraint(
            "description_status IN ('ENRICHED', 'EXISTING_MATCH', 'REVIEW_REQUIRED')",
            name="ck_catalog_position_enrichments_description_status",
        ),
        CheckConstraint(
            "mapping_status IN ('VERIFIED', 'VERIFIED_WITH_NAME_CONFLICT', "
            "'VERIFIED_WITH_ORGANIZATION_CONFLICT')",
            name="ck_catalog_position_enrichments_mapping_status",
        ),
        CheckConstraint(
            "source_page > 0 AND source_slot > 0",
            name="ck_catalog_position_enrichments_locator",
        ),
        CheckConstraint(
            "media_sha256 ~ '^[0-9a-f]{64}$' AND transcript_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_position_enrichments_hashes",
        ),
        CheckConstraint(
            "length(btrim(raw_card)) > 0 AND length(btrim(description_raw)) > 0 "
            "AND length(btrim(description_normalized)) > 0",
            name="ck_catalog_position_enrichments_text",
        ),
        CheckConstraint(
            "jsonb_typeof(normalized_fields) = 'object'",
            name="ck_catalog_position_enrichments_fields_object",
        ),
        ForeignKeyConstraint(
            ["catalog_source_row_id", "catalog_version_id"],
            ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"],
            name="fk_catalog_position_enrichments_source_row_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["transcript_artifact_id"],
            ["source_artifacts.id"],
            name="fk_catalog_position_enrichments_transcript_artifact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["description_import_id"],
            ["catalog_description_imports.id"],
            name="fk_catalog_position_enrichments_import",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_catalog_position_enrichments_version",
            "catalog_version_id",
            "catalog_source_row_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    catalog_source_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transcript_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    description_import_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    source_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    adapter: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    media_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    raw_card: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    description_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    existing_description_snapshot: Mapped[str | None] = mapped_column(Text)
    description_status: Mapped[str] = mapped_column(Text, nullable=False)
    mapping_status: Mapped[str] = mapped_column(Text, nullable=False)
    limitation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EquipmentApplicability(Base):
    __tablename__ = "equipment_applicability"
    __table_args__ = (
        UniqueConstraint(
            "catalog_source_row_id",
            name="uq_equipment_applicability_source_row",
        ),
        UniqueConstraint(
            "id",
            "catalog_version_id",
            name="uq_equipment_applicability_id_version",
        ),
        CheckConstraint(
            "industry IS NULL OR length(btrim(industry)) > 0",
            name="ck_equipment_applicability_industry_nonempty",
        ),
        CheckConstraint(
            "scenario IS NULL OR length(btrim(scenario)) > 0",
            name="ck_equipment_applicability_scenario_nonempty",
        ),
        CheckConstraint(
            "region IS NULL OR length(btrim(region)) > 0",
            name="ck_equipment_applicability_region_nonempty",
        ),
        CheckConstraint(
            "jsonb_typeof(attributes) = 'object'",
            name="ck_equipment_applicability_attributes_object",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_equipment_applicability_catalog_version_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_model_id", "catalog_version_id"],
            ["equipment_models.id", "equipment_models.catalog_version_id"],
            name="fk_equipment_applicability_model_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["catalog_source_row_id", "catalog_version_id"],
            ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"],
            name="fk_equipment_applicability_source_row_version",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    equipment_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    catalog_source_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    industry: Mapped[str | None] = mapped_column(Text)
    scenario: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    case_text: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FieldEvidence(Base):
    __tablename__ = "field_evidence"
    __table_args__ = (
        UniqueConstraint(
            "catalog_version_id",
            "source_namespace",
            "source_record_key",
            name="uq_field_evidence_source_key",
        ),
        UniqueConstraint(
            "id", "catalog_version_id", name="uq_field_evidence_id_version"
        ),
        CheckConstraint(
            "length(btrim(source_namespace)) > 0 AND source_namespace = btrim(source_namespace)",
            name="ck_field_evidence_source_namespace_nonempty",
        ),
        CheckConstraint(
            "length(btrim(source_record_key)) > 0 AND source_record_key = btrim(source_record_key)",
            name="ck_field_evidence_source_record_key_nonempty",
        ),
        CheckConstraint(
            "subject_type IN ('PRODUCT', 'APPLICABILITY', 'PRICE_OFFER', 'SPEC_OBSERVATION')",
            name="ck_field_evidence_subject_type",
        ),
        CheckConstraint(
            "length(btrim(subject_key)) > 0",
            name="ck_field_evidence_subject_key_nonempty",
        ),
        CheckConstraint(
            "length(btrim(field_path)) > 0",
            name="ck_field_evidence_field_path_nonempty",
        ),
        CheckConstraint(
            f"evidence_status IN ({_sql_values(EVIDENCE_STATUSES)})",
            name="ck_field_evidence_status",
        ),
        CheckConstraint(
            "confidence_label IS NULL OR confidence_label IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_field_evidence_confidence_label",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="ck_field_evidence_confidence_score",
        ),
        CheckConstraint(
            "normalized_value IS NULL OR jsonb_typeof(normalized_value) <> 'null'",
            name="ck_field_evidence_normalized_value_not_json_null",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id", "source_artifact_id"],
            [
                "catalog_version_sources.catalog_version_id",
                "catalog_version_sources.source_artifact_id",
            ],
            name="fk_field_evidence_version_artifact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["catalog_source_row_id", "catalog_version_id"],
            ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"],
            name="fk_field_evidence_source_row_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_model_id", "catalog_version_id"],
            ["equipment_models.id", "equipment_models.catalog_version_id"],
            name="fk_field_evidence_model_version",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    catalog_source_row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    equipment_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_key: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_key: Mapped[str] = mapped_column(Text, nullable=False)
    field_path: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    normalized_unit: Mapped[str | None] = mapped_column(Text)
    source_locator: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_label: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    publication_or_update_date: Mapped[date | None] = mapped_column(Date)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SpecObservation(Base):
    __tablename__ = "spec_observations"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(spec_code)) > 0 AND spec_code = btrim(spec_code)",
            name="ck_spec_observations_spec_code_nonempty",
        ),
        CheckConstraint(
            "length(btrim(scope_code)) > 0 AND scope_code = btrim(scope_code)",
            name="ck_spec_observations_scope_code_nonempty",
        ),
        CheckConstraint(
            "num_nonnulls(numeric_value, text_value, boolean_value, json_value) <= 1",
            name="ck_spec_observations_at_most_one_typed_value",
        ),
        CheckConstraint(
            "observation_status IN ('NOT_FOUND', 'UNKNOWN') OR "
            "num_nonnulls(numeric_value, text_value, boolean_value, json_value) = 1",
            name="ck_spec_observations_value_required",
        ),
        CheckConstraint(
            "numeric_value IS NULL OR "
            "(canonical_unit IS NOT NULL AND length(btrim(canonical_unit)) > 0)",
            name="ck_spec_observations_numeric_unit",
        ),
        CheckConstraint(
            f"observation_status IN ({_sql_values(EVIDENCE_STATUSES)})",
            name="ck_spec_observations_status",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_spec_observations_catalog_version_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_model_id", "catalog_version_id"],
            ["equipment_models.id", "equipment_models.catalog_version_id"],
            name="fk_spec_observations_model_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["field_evidence_id", "catalog_version_id"],
            ["field_evidence.id", "field_evidence.catalog_version_id"],
            name="fk_spec_observations_evidence_version",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_spec_observations_model_spec",
            "catalog_version_id",
            "equipment_model_id",
            "spec_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    equipment_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    field_evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    spec_code: Mapped[str] = mapped_column(Text, nullable=False)
    scope_code: Mapped[str] = mapped_column(
        Text, nullable=False, default="GLOBAL", server_default=text("'GLOBAL'")
    )
    raw_value: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    text_value: Mapped[str | None] = mapped_column(Text)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    json_value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    canonical_unit: Mapped[str | None] = mapped_column(Text)
    observation_status: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResolvedSpecFact(Base):
    __tablename__ = "resolved_spec_facts"
    __table_args__ = (
        UniqueConstraint(
            "catalog_version_id",
            "equipment_model_id",
            "spec_code",
            "scope_code",
            name="uq_resolved_spec_facts_model_spec_scope",
        ),
        UniqueConstraint(
            "id", "catalog_version_id", name="uq_resolved_spec_facts_id_version"
        ),
        CheckConstraint(
            "length(btrim(spec_code)) > 0 AND spec_code = btrim(spec_code)",
            name="ck_resolved_spec_facts_spec_code_nonempty",
        ),
        CheckConstraint(
            "length(btrim(scope_code)) > 0 AND scope_code = btrim(scope_code)",
            name="ck_resolved_spec_facts_scope_code_nonempty",
        ),
        CheckConstraint(
            "num_nonnulls(numeric_value, text_value, boolean_value, json_value) = 1",
            name="ck_resolved_spec_facts_exactly_one_typed_value",
        ),
        CheckConstraint(
            "length(btrim(canonical_unit)) > 0",
            name="ck_resolved_spec_facts_canonical_unit_nonempty",
        ),
        CheckConstraint(
            f"resolution_status IN ({_sql_values(RESOLUTION_STATUSES)})",
            name="ck_resolved_spec_facts_status",
        ),
        CheckConstraint(
            "NOT usable_for_matching OR resolution_status IN "
            f"({_sql_values(SAFE_AUTOMATIC_STATUSES + REVIEWED_STATUSES)})",
            name="ck_resolved_spec_facts_matching_safe_status",
        ),
        CheckConstraint(
            "resolution_status NOT IN "
            f"({_sql_values(REVIEWED_STATUSES)}) OR "
            "(reviewed_by_subject IS NOT NULL AND length(btrim(reviewed_by_subject)) > 0 "
            "AND review_reason IS NOT NULL AND length(btrim(review_reason)) > 0 "
            "AND reviewed_at IS NOT NULL)",
            name="ck_resolved_spec_facts_review_metadata",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_resolved_spec_facts_catalog_version_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_model_id", "catalog_version_id"],
            ["equipment_models.id", "equipment_models.catalog_version_id"],
            name="fk_resolved_spec_facts_model_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["primary_evidence_id", "catalog_version_id"],
            ["field_evidence.id", "field_evidence.catalog_version_id"],
            name="fk_resolved_spec_facts_primary_evidence_version",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_resolved_spec_facts_matching_lookup",
            "catalog_version_id",
            "spec_code",
            "numeric_value",
            postgresql_where=text("usable_for_matching"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    equipment_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    primary_evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    spec_code: Mapped[str] = mapped_column(Text, nullable=False)
    scope_code: Mapped[str] = mapped_column(
        Text, nullable=False, default="GLOBAL", server_default=text("'GLOBAL'")
    )
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    text_value: Mapped[str | None] = mapped_column(Text)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    json_value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    canonical_unit: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_status: Mapped[str] = mapped_column(Text, nullable=False)
    usable_for_matching: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    reviewed_by_subject: Mapped[str | None] = mapped_column(Text)
    review_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResolvedSpecFactEvidence(Base):
    __tablename__ = "resolved_spec_fact_evidence"
    __table_args__ = (
        PrimaryKeyConstraint(
            "resolved_spec_fact_id",
            "field_evidence_id",
            name="pk_resolved_spec_fact_evidence",
        ),
        ForeignKeyConstraint(
            ["resolved_spec_fact_id", "catalog_version_id"],
            ["resolved_spec_facts.id", "resolved_spec_facts.catalog_version_id"],
            name="fk_resolved_fact_evidence_fact_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["field_evidence_id", "catalog_version_id"],
            ["field_evidence.id", "field_evidence.catalog_version_id"],
            name="fk_resolved_fact_evidence_evidence_version",
            ondelete="RESTRICT",
        ),
    )

    resolved_spec_fact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    field_evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )


class ProcurementOption(Base):
    __tablename__ = "procurement_options"
    __table_args__ = (
        UniqueConstraint(
            "catalog_source_row_id", name="uq_procurement_options_source_row"
        ),
        CheckConstraint(
            "procurement_mode IN ('PURCHASE', 'LEASE', 'RENTAL', 'RAAS', 'MANAGED_SERVICE', 'QUOTE')",
            name="ck_procurement_options_mode",
        ),
        CheckConstraint(
            "price_status IN ('RAW_UNRESOLVED', 'NORMALIZED', 'QUOTE_REQUIRED', 'UNKNOWN')",
            name="ck_procurement_options_price_status",
        ),
        CheckConstraint(
            "amount IS NULL OR amount >= 0", name="ck_procurement_options_amount"
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="ck_procurement_options_currency",
        ),
        CheckConstraint(
            "currency IS NULL OR (currency_provenance IS NOT NULL AND length(btrim(currency_provenance)) > 0)",
            name="ck_procurement_options_currency_provenance",
        ),
        CheckConstraint(
            "vat_status IN ('UNKNOWN', 'ORGANIZER_ASSUMPTION_INCLUDED', 'INCLUDED', 'EXCLUDED', 'NOT_APPLICABLE')",
            name="ck_procurement_options_vat_status",
        ),
        CheckConstraint(
            "vat_rate IS NULL OR vat_rate BETWEEN 0 AND 1",
            name="ck_procurement_options_vat_rate",
        ),
        CheckConstraint(
            "vat_status <> 'ORGANIZER_ASSUMPTION_INCLUDED' OR "
            "(vat_rate IS NULL AND vat_provenance IS NOT NULL AND length(btrim(vat_provenance)) > 0)",
            name="ck_procurement_options_organizer_vat_assumption",
        ),
        CheckConstraint(
            "jsonb_typeof(included_costs) = 'array'",
            name="ck_procurement_options_included_costs_array",
        ),
        CheckConstraint(
            "jsonb_typeof(excluded_costs) = 'array'",
            name="ck_procurement_options_excluded_costs_array",
        ),
        ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_procurement_options_catalog_version_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_model_id", "catalog_version_id"],
            ["equipment_models.id", "equipment_models.catalog_version_id"],
            name="fk_procurement_options_model_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["catalog_source_row_id", "catalog_version_id"],
            ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"],
            name="fk_procurement_options_source_row_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["field_evidence_id", "catalog_version_id"],
            ["field_evidence.id", "field_evidence.catalog_version_id"],
            name="fk_procurement_options_evidence_version",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    equipment_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    catalog_source_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    field_evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    procurement_mode: Mapped[str] = mapped_column(Text, nullable=False)
    raw_price: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    currency: Mapped[str | None] = mapped_column(Text)
    currency_provenance: Mapped[str | None] = mapped_column(Text)
    vat_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="UNKNOWN", server_default=text("'UNKNOWN'")
    )
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    vat_provenance: Mapped[str | None] = mapped_column(Text)
    price_status: Mapped[str] = mapped_column(Text, nullable=False)
    included_costs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    excluded_costs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
