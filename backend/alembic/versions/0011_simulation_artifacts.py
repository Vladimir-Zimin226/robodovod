"""Add separate immutable C23 evidence bound to a saved analysis run.

Revision ID: 0011_simulation_artifacts
Revises: 0010_economics_runtime_migration

No existing analysis_runs row is changed or backfilled. Applying this revision
does not activate a route or alter production traffic.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_simulation_artifacts"
down_revision: str | None = "0010_economics_runtime_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("artifact_version", sa.Text(), nullable=False),
        sa.Column("request_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("report_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("request_sha256", sa.Text(), nullable=False),
        sa.Column("report_sha256", sa.Text(), nullable=False),
        sa.Column("scenario_spec_sha256", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("analysis_run_id", "request_id", name="uq_simulation_artifacts_run_request"),
        sa.CheckConstraint("artifact_version = 'simulation-artifact-v1'", name="ck_simulation_artifacts_version"),
        sa.CheckConstraint("jsonb_typeof(request_snapshot) = 'object'", name="ck_simulation_artifacts_request_object"),
        sa.CheckConstraint("jsonb_typeof(report_snapshot) = 'object'", name="ck_simulation_artifacts_report_object"),
        sa.CheckConstraint("request_sha256 ~ '^[0-9a-f]{64}$'", name="ck_simulation_artifacts_request_sha256"),
        sa.CheckConstraint("report_sha256 ~ '^[0-9a-f]{64}$'", name="ck_simulation_artifacts_report_sha256"),
        sa.CheckConstraint("scenario_spec_sha256 ~ '^[0-9a-f]{64}$'", name="ck_simulation_artifacts_spec_sha256"),
    )
    op.create_index("ix_simulation_artifacts_run_created", "simulation_artifacts", ["analysis_run_id", "created_at"])
    op.execute(
        "CREATE FUNCTION prevent_simulation_artifact_update() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'simulation artifact is immutable'; END; "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER trg_simulation_artifacts_immutable "
        "BEFORE UPDATE ON simulation_artifacts FOR EACH ROW "
        "EXECUTE FUNCTION prevent_simulation_artifact_update()"
    )


def downgrade() -> None:
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM simulation_artifacts) "
               "THEN RAISE EXCEPTION 'cannot downgrade while simulation evidence exists'; "
               "END IF; END $$")
    op.execute("DROP TRIGGER trg_simulation_artifacts_immutable ON simulation_artifacts")
    op.execute("DROP FUNCTION prevent_simulation_artifact_update()")
    op.drop_index("ix_simulation_artifacts_run_created", table_name="simulation_artifacts")
    op.drop_table("simulation_artifacts")
