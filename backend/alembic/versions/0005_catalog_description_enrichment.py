"""add append-only catalog position description enrichment

Revision ID: 0005_catalog_description
Revises: 0004_catalog_position_media
Create Date: 2026-09-17 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_catalog_description"
down_revision: str | None = "0004_catalog_position_media"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_description_imports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("catalog_version_id", sa.UUID(), nullable=False),
        sa.Column("overlay_sha256", sa.Text(), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("overlay_sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_description_imports_overlay_sha256"),
        sa.CheckConstraint("jsonb_typeof(report) = 'object'", name="ck_catalog_description_imports_report_object"),
        sa.ForeignKeyConstraint(["catalog_version_id"], ["catalog_versions.id"], name="fk_catalog_description_imports_version", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_version_id", name="uq_catalog_description_imports_version"),
    )
    op.create_table(
        "catalog_position_enrichments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("catalog_version_id", sa.UUID(), nullable=False),
        sa.Column("catalog_source_row_id", sa.UUID(), nullable=False),
        sa.Column("transcript_artifact_id", sa.UUID(), nullable=False),
        sa.Column("description_import_id", sa.UUID(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("source_slot", sa.Integer(), nullable=False),
        sa.Column("adapter", sa.Text(), nullable=False),
        sa.Column("transcript_sha256", sa.Text(), nullable=False),
        sa.Column("media_sha256", sa.Text(), nullable=False),
        sa.Column("raw_card", sa.Text(), nullable=False),
        sa.Column("normalized_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column("description_normalized", sa.Text(), nullable=False),
        sa.Column("existing_description_snapshot", sa.Text(), nullable=True),
        sa.Column("description_status", sa.Text(), nullable=False),
        sa.Column("mapping_status", sa.Text(), nullable=False),
        sa.Column("limitation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("adapter IN ('page-oriented-v1', 'field-oriented-v1')", name="ck_catalog_position_enrichments_adapter"),
        sa.CheckConstraint("description_status IN ('ENRICHED', 'EXISTING_MATCH', 'REVIEW_REQUIRED')", name="ck_catalog_position_enrichments_description_status"),
        sa.CheckConstraint("mapping_status IN ('VERIFIED', 'VERIFIED_WITH_NAME_CONFLICT', 'VERIFIED_WITH_ORGANIZATION_CONFLICT')", name="ck_catalog_position_enrichments_mapping_status"),
        sa.CheckConstraint("source_page > 0 AND source_slot > 0", name="ck_catalog_position_enrichments_locator"),
        sa.CheckConstraint("media_sha256 ~ '^[0-9a-f]{64}$' AND transcript_sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_position_enrichments_hashes"),
        sa.CheckConstraint("length(btrim(raw_card)) > 0 AND length(btrim(description_raw)) > 0 AND length(btrim(description_normalized)) > 0", name="ck_catalog_position_enrichments_text"),
        sa.CheckConstraint("jsonb_typeof(normalized_fields) = 'object'", name="ck_catalog_position_enrichments_fields_object"),
        sa.ForeignKeyConstraint(["catalog_source_row_id", "catalog_version_id"], ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"], name="fk_catalog_position_enrichments_source_row_version", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transcript_artifact_id"], ["source_artifacts.id"], name="fk_catalog_position_enrichments_transcript_artifact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["description_import_id"], ["catalog_description_imports.id"], name="fk_catalog_position_enrichments_import", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_source_row_id", name="uq_catalog_position_enrichments_source_row"),
        sa.UniqueConstraint("catalog_version_id", "source_page", "source_slot", name="uq_catalog_position_enrichments_locator"),
    )
    op.create_index("ix_catalog_position_enrichments_version", "catalog_position_enrichments", ["catalog_version_id", "catalog_source_row_id"])
    op.execute(
        """
        CREATE FUNCTION enforce_catalog_description_append_only()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE version_status text;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'catalog description enrichment is append-only'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_catalog_description_append_only';
            END IF;
            SELECT status INTO version_status FROM catalog_versions
            WHERE id = NEW.catalog_version_id FOR UPDATE;
            IF version_status NOT IN ('DRAFT', 'PUBLISHED') THEN
                RAISE EXCEPTION 'catalog description enrichment requires a draft or published version'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_catalog_description_version_status';
            END IF;
            RETURN NEW;
        END; $$
        """
    )
    for table in ("catalog_description_imports", "catalog_position_enrichments"):
        op.execute(f"CREATE TRIGGER trg_{table}_append_only BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION enforce_catalog_description_append_only()")


def downgrade() -> None:
    for table in ("catalog_position_enrichments", "catalog_description_imports"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS enforce_catalog_description_append_only()")
    op.drop_index("ix_catalog_position_enrichments_version", table_name="catalog_position_enrichments")
    op.drop_table("catalog_position_enrichments")
    op.drop_table("catalog_description_imports")
