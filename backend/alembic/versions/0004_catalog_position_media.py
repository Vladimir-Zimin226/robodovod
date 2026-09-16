"""add append-only catalog position media

Revision ID: 0004_catalog_position_media
Revises: 0003_projects_analysis_runs
Create Date: 2026-09-17 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_catalog_position_media"
down_revision: str | None = "0003_projects_analysis_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_media_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("catalog_version_id", sa.UUID(), nullable=False),
        sa.Column("source_artifact_id", sa.UUID(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_media_assets_sha256"
        ),
        sa.CheckConstraint(
            "media_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name="ck_catalog_media_assets_media_type",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_catalog_media_assets_byte_size"),
        sa.CheckConstraint(
            "width_px > 0 AND height_px > 0",
            name="ck_catalog_media_assets_dimensions",
        ),
        sa.CheckConstraint(
            "storage_key = btrim(storage_key) AND length(storage_key) > 0",
            name="ck_catalog_media_assets_storage_key",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id", "source_artifact_id"],
            [
                "catalog_version_sources.catalog_version_id",
                "catalog_version_sources.source_artifact_id",
            ],
            name="fk_catalog_media_assets_version_artifact",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "catalog_version_id", name="uq_catalog_media_assets_id_version"
        ),
        sa.UniqueConstraint(
            "catalog_version_id",
            "sha256",
            name="uq_catalog_media_assets_version_sha256",
        ),
        sa.UniqueConstraint("storage_key", name="uq_catalog_media_assets_storage_key"),
    )
    op.create_table(
        "catalog_position_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("catalog_version_id", sa.UUID(), nullable=False),
        sa.Column("catalog_source_row_id", sa.UUID(), nullable=False),
        sa.Column("media_asset_id", sa.UUID(), nullable=False),
        sa.Column(
            "role", sa.Text(), server_default=sa.text("'PRIMARY'"), nullable=False
        ),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("source_slot", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('PRIMARY')", name="ck_catalog_position_media_role"
        ),
        sa.CheckConstraint(
            "source_page > 0 AND source_slot > 0",
            name="ck_catalog_position_media_source_locator",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_source_row_id", "catalog_version_id"],
            ["catalog_source_rows.id", "catalog_source_rows.catalog_version_id"],
            name="fk_catalog_position_media_source_row_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id", "catalog_version_id"],
            ["catalog_media_assets.id", "catalog_media_assets.catalog_version_id"],
            name="fk_catalog_position_media_asset_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_source_row_id",
            "role",
            name="uq_catalog_position_media_source_row_role",
        ),
        sa.UniqueConstraint(
            "catalog_version_id",
            "source_page",
            "source_slot",
            name="uq_catalog_position_media_source_locator",
        ),
    )
    op.create_index(
        "ix_catalog_position_media_version",
        "catalog_position_media",
        ["catalog_version_id", "catalog_source_row_id"],
    )
    op.execute(
        """
        CREATE FUNCTION enforce_catalog_media_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            version_status text;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'catalog media metadata is append-only'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_media_append_only';
            END IF;

            SELECT status INTO version_status
            FROM catalog_versions
            WHERE id = NEW.catalog_version_id
            FOR UPDATE;

            IF version_status NOT IN ('DRAFT', 'PUBLISHED') THEN
                RAISE EXCEPTION 'catalog media requires a draft or published version'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_media_version_status';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    for table_name in ("catalog_media_assets", "catalog_position_media"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_append_only
            BEFORE INSERT OR UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION enforce_catalog_media_append_only()
            """
        )


def downgrade() -> None:
    for table_name in ("catalog_position_media", "catalog_media_assets"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}"
        )
    op.execute("DROP FUNCTION IF EXISTS enforce_catalog_media_append_only()")
    op.drop_index(
        "ix_catalog_position_media_version", table_name="catalog_position_media"
    )
    op.drop_table("catalog_position_media")
    op.drop_table("catalog_media_assets")
