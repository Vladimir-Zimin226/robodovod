"""Versioned admin catalog documents. No updates to existing catalog or runs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_admin_catalog"
down_revision = "0011_simulation_artifacts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_catalog_documents",
        sa.Column(
            "catalog_version_id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("import_sha256", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"], ["catalog_versions.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("revision > 0", name="ck_admin_catalog_revision"),
        sa.CheckConstraint(
            "jsonb_typeof(document) = 'object'", name="ck_admin_catalog_document"
        ),
        sa.CheckConstraint(
            "import_sha256 IS NULL OR import_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_admin_catalog_import_sha",
        ),
    )
    op.execute("""
        CREATE FUNCTION protect_admin_catalog_document() RETURNS trigger AS $$
        DECLARE state text;
        BEGIN
          SELECT status INTO state FROM catalog_versions
            WHERE id = COALESCE(NEW.catalog_version_id, OLD.catalog_version_id) FOR SHARE;
          IF state IN ('PUBLISHED', 'RETIRED') THEN
            RAISE EXCEPTION 'published admin catalog document is immutable';
          END IF;
          IF TG_OP = 'UPDATE' AND (NEW.owner_id <> OLD.owner_id OR
              NEW.catalog_version_id <> OLD.catalog_version_id OR NEW.created_at <> OLD.created_at) THEN
            RAISE EXCEPTION 'admin catalog identity is immutable';
          END IF;
          RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER admin_catalog_document_guard BEFORE INSERT OR UPDATE OR DELETE
          ON admin_catalog_documents FOR EACH ROW EXECUTE FUNCTION protect_admin_catalog_document();
    """)


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM admin_catalog_documents d JOIN catalog_versions v
                   ON v.id=d.catalog_version_id WHERE v.status IN ('PUBLISHED','RETIRED')) THEN
            RAISE EXCEPTION 'cannot downgrade while published admin catalog history exists';
        END IF; END $$""")
    op.drop_table("admin_catalog_documents")
    op.execute("DROP FUNCTION protect_admin_catalog_document()")
