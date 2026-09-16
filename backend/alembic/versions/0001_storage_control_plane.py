"""Create the storage control-plane.

Revision ID: 0001_storage_control_plane
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_storage_control_plane"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SHA256_CHECK = "^[0-9a-f]{64}$"


def upgrade() -> None:
    op.create_table(
        "catalog_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(btrim(code)) > 0 AND code = btrim(code)",
            name="ck_catalog_versions_code_nonempty",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'VALIDATED', 'PUBLISHED', 'RETIRED')",
            name="ck_catalog_versions_status",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) > 0 AND schema_version = btrim(schema_version)",
            name="ck_catalog_versions_schema_version_nonempty",
        ),
        sa.CheckConstraint(
            f"content_sha256 IS NULL OR content_sha256 ~ '{SHA256_CHECK}'",
            name="ck_catalog_versions_content_sha256",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ck_catalog_versions_updated_after_created",
        ),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND validated_at IS NULL AND published_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'VALIDATED' AND validated_at IS NOT NULL AND published_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'PUBLISHED' AND validated_at IS NOT NULL AND published_at IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'RETIRED' AND validated_at IS NOT NULL AND published_at IS NOT NULL AND retired_at IS NOT NULL)",
            name="ck_catalog_versions_lifecycle_presence",
        ),
        sa.CheckConstraint(
            "(validated_at IS NULL OR validated_at >= created_at) AND "
            "(published_at IS NULL OR published_at >= validated_at) AND "
            "(retired_at IS NULL OR retired_at >= published_at)",
            name="ck_catalog_versions_lifecycle_order",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["catalog_versions.id"],
            name="fk_catalog_versions_parent_version_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_versions"),
        sa.UniqueConstraint("code", name="uq_catalog_versions_code"),
    )

    op.create_table(
        "source_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("provenance_status", sa.Text(), nullable=False),
        sa.Column("license_status", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"sha256 ~ '{SHA256_CHECK}'", name="ck_source_artifacts_sha256"
        ),
        sa.CheckConstraint(
            "length(btrim(original_name)) > 0",
            name="ck_source_artifacts_original_name_nonempty",
        ),
        sa.CheckConstraint(
            "length(btrim(media_type)) > 0",
            name="ck_source_artifacts_media_type_nonempty",
        ),
        sa.CheckConstraint(
            "byte_size > 0", name="ck_source_artifacts_byte_size_positive"
        ),
        sa.CheckConstraint(
            "storage_key IS NULL OR length(btrim(storage_key)) > 0",
            name="ck_source_artifacts_storage_key_nonempty",
        ),
        sa.CheckConstraint(
            "provenance_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="ck_source_artifacts_provenance_status",
        ),
        sa.CheckConstraint(
            "license_status IN ('UNKNOWN', 'PERMITTED', 'RESTRICTED')",
            name="ck_source_artifacts_license_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_artifacts"),
        sa.UniqueConstraint("sha256", name="uq_source_artifacts_sha256"),
    )

    op.create_table(
        "catalog_version_sources",
        sa.Column(
            "catalog_version_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "source_artifact_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "role IN ('BASE', 'ENRICHMENT', 'REFERENCE', 'IMPORT_BUNDLE')",
            name="ck_catalog_version_sources_role",
        ),
        sa.CheckConstraint(
            "ordinal >= 0", name="ck_catalog_version_sources_ordinal"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_catalog_version_sources_catalog_version_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["source_artifacts.id"],
            name="fk_catalog_version_sources_source_artifact_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "catalog_version_id",
            "source_artifact_id",
            name="pk_catalog_version_sources",
        ),
        sa.UniqueConstraint(
            "catalog_version_id",
            "role",
            "ordinal",
            name="uq_catalog_version_sources_role_ordinal",
        ),
    )

    op.create_table(
        "import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "catalog_version_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("bundle_sha256", sa.Text(), nullable=False),
        sa.Column("request_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "phase IN ('BASE', 'ENRICHMENT')", name="ck_import_runs_phase"
        ),
        sa.CheckConstraint(
            "mode IN ('VALIDATE_ONLY', 'COMMIT')", name="ck_import_runs_mode"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_import_runs_status",
        ),
        sa.CheckConstraint(
            f"bundle_sha256 ~ '{SHA256_CHECK}'",
            name="ck_import_runs_bundle_sha256",
        ),
        sa.CheckConstraint(
            "request_key IS NULL OR length(btrim(request_key)) > 0",
            name="ck_import_runs_request_key_nonempty",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(counts) = 'object'", name="ck_import_runs_counts_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(diagnostics) = 'object'",
            name="ck_import_runs_diagnostics_object",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
            "(status IN ('SUCCEEDED', 'FAILED') AND started_at IS NOT NULL AND finished_at IS NOT NULL)",
            name="ck_import_runs_status_timestamps",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_import_runs_finished_after_started",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_import_runs_catalog_version_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_runs"),
        sa.UniqueConstraint("request_key", name="uq_import_runs_request_key"),
    )
    op.create_index(
        "uq_import_runs_successful_commit",
        "import_runs",
        ["catalog_version_id", "phase", "bundle_sha256"],
        unique=True,
        postgresql_where=sa.text("status = 'SUCCEEDED' AND mode = 'COMMIT'"),
    )

    op.create_table(
        "catalog_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column(
            "catalog_version_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_subject", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "length(btrim(slot)) > 0 AND slot = btrim(slot)",
            name="ck_catalog_activations_slot_nonempty",
        ),
        sa.CheckConstraint(
            "actor_subject IS NULL OR length(btrim(actor_subject)) > 0",
            name="ck_catalog_activations_actor_subject_nonempty",
        ),
        sa.CheckConstraint(
            "deactivated_at IS NULL OR deactivated_at >= activated_at",
            name="ck_catalog_activations_timestamp_order",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"],
            ["catalog_versions.id"],
            name="fk_catalog_activations_catalog_version_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_activations"),
    )
    op.create_index(
        "uq_catalog_activations_active_slot",
        "catalog_activations",
        ["slot"],
        unique=True,
        postgresql_where=sa.text("deactivated_at IS NULL"),
    )

    op.execute(
        """
        CREATE FUNCTION enforce_catalog_version_status_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status
               AND NOT (
                   (OLD.status = 'DRAFT' AND NEW.status = 'VALIDATED') OR
                   (OLD.status = 'VALIDATED' AND NEW.status = 'PUBLISHED') OR
                   (OLD.status = 'PUBLISHED' AND NEW.status = 'RETIRED')
               ) THEN
                RAISE EXCEPTION 'invalid catalog version status transition'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_versions_status_transition';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_versions_status_transition
        BEFORE UPDATE OF status ON catalog_versions
        FOR EACH ROW
        EXECUTE FUNCTION enforce_catalog_version_status_transition()
        """
    )

    op.execute(
        """
        CREATE FUNCTION ensure_catalog_activation_published()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM catalog_versions
                WHERE id = NEW.catalog_version_id AND status = 'PUBLISHED'
            ) THEN
                RAISE EXCEPTION 'catalog activation requires a PUBLISHED version'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_activations_published_version';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_catalog_activations_published_version
        AFTER INSERT OR UPDATE ON catalog_activations
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION ensure_catalog_activation_published()
        """
    )

    op.execute(
        """
        CREATE FUNCTION preserve_catalog_activation_history()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'catalog activation history cannot be deleted'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_activations_immutable';
            END IF;

            IF OLD.deactivated_at IS NOT NULL
               OR NEW.deactivated_at IS NULL
               OR ROW(
                   NEW.id,
                   NEW.slot,
                   NEW.catalog_version_id,
                   NEW.activated_at,
                   NEW.actor_subject
               ) IS DISTINCT FROM ROW(
                   OLD.id,
                   OLD.slot,
                   OLD.catalog_version_id,
                   OLD.activated_at,
                   OLD.actor_subject
               ) THEN
                RAISE EXCEPTION 'catalog activation history is immutable'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_activations_immutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_activations_immutable_update
        BEFORE UPDATE ON catalog_activations
        FOR EACH ROW
        EXECUTE FUNCTION preserve_catalog_activation_history()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_activations_immutable_delete
        BEFORE DELETE ON catalog_activations
        FOR EACH ROW
        EXECUTE FUNCTION preserve_catalog_activation_history()
        """
    )

    op.execute(
        """
        CREATE FUNCTION ensure_active_catalog_version_published()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status <> 'PUBLISHED' AND EXISTS (
                SELECT 1
                FROM catalog_activations
                WHERE catalog_version_id = NEW.id AND deactivated_at IS NULL
            ) THEN
                RAISE EXCEPTION 'an active catalog version must remain PUBLISHED'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_catalog_versions_active_published';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_catalog_versions_active_published
        AFTER UPDATE OF status ON catalog_versions
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION ensure_active_catalog_version_published()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_versions_active_published ON catalog_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS ensure_active_catalog_version_published()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_activations_immutable_delete ON catalog_activations"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_activations_immutable_update ON catalog_activations"
    )
    op.execute("DROP FUNCTION IF EXISTS preserve_catalog_activation_history()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_activations_published_version ON catalog_activations"
    )
    op.execute("DROP FUNCTION IF EXISTS ensure_catalog_activation_published()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_versions_status_transition ON catalog_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_catalog_version_status_transition()")

    op.drop_index(
        "uq_catalog_activations_active_slot", table_name="catalog_activations"
    )
    op.drop_table("catalog_activations")
    op.drop_index("uq_import_runs_successful_commit", table_name="import_runs")
    op.drop_table("import_runs")
    op.drop_table("catalog_version_sources")
    op.drop_table("source_artifacts")
    op.drop_table("catalog_versions")
