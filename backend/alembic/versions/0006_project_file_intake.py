"""Store validated project file import snapshots.

Revision ID: 0006_project_file_intake
Revises: 0005_catalog_description
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_project_file_intake"
down_revision: str | None = "0005_catalog_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_file_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_code", sa.Text(), nullable=False),
        sa.Column("file_format", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("normalized_input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("profile_code IN ('warehouse', 'airport', 'medical_facility')", name="ck_project_file_imports_profile"),
        sa.CheckConstraint("file_format IN ('XLSX', 'CSV')", name="ck_project_file_imports_format"),
        sa.CheckConstraint("length(btrim(profile_version)) > 0", name="ck_project_file_imports_profile_version"),
        sa.CheckConstraint("jsonb_typeof(normalized_input) = 'object'", name="ck_project_file_imports_input_object"),
        sa.CheckConstraint("jsonb_typeof(provenance) = 'object'", name="ck_project_file_imports_provenance_object"),
        sa.CheckConstraint("jsonb_typeof(validation_report) = 'object'", name="ck_project_file_imports_report_object"),
        sa.ForeignKeyConstraint(["project_file_id"], ["project_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_file_id", name="uq_project_file_imports_file"),
    )
    op.create_index(
        "ix_project_file_imports_scenario",
        "project_file_imports",
        ["scenario_id", "applied_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_file_imports_scenario", table_name="project_file_imports")
    op.drop_table("project_file_imports")
