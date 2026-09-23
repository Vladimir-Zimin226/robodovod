"""Add immutable economics version mappings and route activation history.

Revision ID: 0010_economics_runtime_migration
Revises: 0009_capacity_catalog_rollout
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_economics_runtime_migration"
down_revision: str | None = "0009_capacity_catalog_rollout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHA = "^[0-9a-f]{64}$"


def upgrade() -> None:
    op.create_table(
        "analysis_run_economics_versions",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_route", sa.Text(), nullable=False),
        sa.Column("economics_version", sa.Text(), nullable=False),
        sa.Column("viewer_version", sa.Text(), nullable=False),
        sa.Column("replay_mode", sa.Text(), nullable=False),
        sa.Column("rerun_mode", sa.Text(), nullable=False),
        sa.Column("fte_basis_status", sa.Text(), nullable=False),
        sa.Column("migration_notice", sa.Text(), nullable=False),
        sa.Column("mapped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("execution_route IN ('LEGACY_V1', 'ECONOMICS_V2')", name="ck_run_economics_versions_route"),
        sa.CheckConstraint("economics_version IN ('legacy-economics-v1', 'economics-runtime-v2')", name="ck_run_economics_versions_version"),
        sa.CheckConstraint("viewer_version IN ('legacy-snapshot-viewer-v1', 'commercial-scenarios-viewer-v2')", name="ck_run_economics_versions_viewer"),
        sa.CheckConstraint("replay_mode IN ('SAVED_SNAPSHOT_ONLY', 'DETERMINISTIC_V2')", name="ck_run_economics_versions_replay"),
        sa.CheckConstraint("rerun_mode = 'CREATE_NEW_RUN_ON_ACTIVE_ROUTE'", name="ck_run_economics_versions_rerun"),
        sa.CheckConstraint("fte_basis_status IN ('NOT_APPLICABLE', 'UNKNOWN_LEGACY_BASIS', 'EXPLICIT_GROSS', 'MISSING_GROSS')", name="ck_run_economics_versions_fte_basis"),
        sa.CheckConstraint(
            "(execution_route = 'LEGACY_V1' AND economics_version = 'legacy-economics-v1' "
            "AND viewer_version = 'legacy-snapshot-viewer-v1' AND replay_mode = 'SAVED_SNAPSHOT_ONLY' "
            "AND fte_basis_status IN ('NOT_APPLICABLE', 'UNKNOWN_LEGACY_BASIS')) OR "
            "(execution_route = 'ECONOMICS_V2' AND economics_version = 'economics-runtime-v2' "
            "AND viewer_version = 'commercial-scenarios-viewer-v2' AND replay_mode = 'DETERMINISTIC_V2' "
            "AND fte_basis_status IN ('EXPLICIT_GROSS', 'MISSING_GROSS'))",
            name="ck_run_economics_versions_consistent",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.execute(
        "INSERT INTO analysis_run_economics_versions "
        "(run_id, execution_route, economics_version, viewer_version, replay_mode, "
        "rerun_mode, fte_basis_status, migration_notice) "
        "SELECT id, 'LEGACY_V1', 'legacy-economics-v1', 'legacy-snapshot-viewer-v1', "
        "'SAVED_SNAPSHOT_ONLY', 'CREATE_NEW_RUN_ON_ACTIVE_ROUTE', "
        "CASE WHEN input_snapshot ? 'fte_cost_rub' THEN 'UNKNOWN_LEGACY_BASIS' ELSE 'NOT_APPLICABLE' END, "
        "CASE WHEN input_snapshot ? 'fte_cost_rub' "
        "THEN 'Legacy result is preserved exactly. Re-run requires explicit monthly gross and payroll basis; fte_cost_rub is not converted.' "
        "ELSE 'Legacy result is preserved exactly; re-run creates a new v2 run.' END "
        "FROM analysis_runs WHERE run_kind = 'FULL_ANALYSIS' "
        "AND economics_version = 'legacy-economics-v1'"
    )
    op.execute(
        "CREATE FUNCTION prevent_economics_mapping_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'analysis run economics mapping is immutable'; END; "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER trg_analysis_run_economics_versions_immutable "
        "BEFORE UPDATE ON analysis_run_economics_versions FOR EACH ROW "
        "EXECUTE FUNCTION prevent_economics_mapping_mutation()"
    )

    op.create_table(
        "economics_route_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("economics_version", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("approval_report_sha256", sa.Text(), nullable=False),
        sa.Column("rollback_economics_version", sa.Text(), nullable=False),
        sa.Column("actor_subject", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("economics_version IN ('legacy-economics-v1', 'economics-runtime-v2')", name="ck_economics_route_activations_version"),
        sa.CheckConstraint("rollback_economics_version IN ('legacy-economics-v1', 'economics-runtime-v2')", name="ck_economics_route_activations_rollback"),
        sa.CheckConstraint(f"approval_report_sha256 ~ '{SHA}'", name="ck_economics_route_activations_approval_sha"),
        sa.CheckConstraint("deactivated_at IS NULL OR deactivated_at >= activated_at", name="ck_economics_route_activations_time_order"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_economics_route_activations_active",
        "economics_route_activations",
        [sa.text("(1)")],
        unique=True,
        postgresql_where=sa.text("deactivated_at IS NULL"),
    )
    # Deliberately no activation seed: applying this migration cannot switch production.


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM economics_route_activations) OR EXISTS "
        "(SELECT 1 FROM analysis_run_economics_versions WHERE economics_version = 'economics-runtime-v2') "
        "THEN RAISE EXCEPTION 'cannot downgrade while economics rollout history exists'; "
        "END IF; END $$"
    )
    op.drop_index("uq_economics_route_activations_active", table_name="economics_route_activations")
    op.drop_table("economics_route_activations")
    op.execute("DROP TRIGGER trg_analysis_run_economics_versions_immutable ON analysis_run_economics_versions")
    op.execute("DROP FUNCTION prevent_economics_mapping_mutation()")
    op.drop_table("analysis_run_economics_versions")
