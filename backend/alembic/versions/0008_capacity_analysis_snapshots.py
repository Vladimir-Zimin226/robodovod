"""Add per-kind immutable capacity analysis snapshots.

Revision ID: 0008_capacity_snapshots
Revises: 0007_file_parameter_values
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_capacity_snapshots"
down_revision: str | None = "0007_file_parameter_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHA = "^[0-9a-f]{64}$"


def _state_constraint() -> str:
    return (
        "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL AND result_snapshot IS NULL "
        "AND scenario_spec_snapshot IS NULL AND trace_snapshot IS NULL) OR "
        "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL AND result_snapshot IS NULL "
        "AND scenario_spec_snapshot IS NULL AND trace_snapshot IS NULL) OR "
        "(status = 'SUCCEEDED' AND run_kind = 'FULL_ANALYSIS' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND result_snapshot IS NOT NULL AND result_sha256 IS NOT NULL AND scenario_spec_snapshot IS NOT NULL "
        "AND scenario_spec_sha256 IS NOT NULL AND trace_snapshot IS NULL AND trace_sha256 IS NULL) OR "
        "(status = 'SUCCEEDED' AND run_kind = 'CAPACITY_ANALYSIS' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND result_snapshot IS NOT NULL AND result_sha256 IS NOT NULL AND scenario_spec_snapshot IS NULL "
        "AND scenario_spec_sha256 IS NULL AND trace_snapshot IS NOT NULL AND trace_sha256 IS NOT NULL "
        "AND version_bindings_snapshot IS NOT NULL AND version_bindings_sha256 IS NOT NULL) OR "
        "(status IN ('FAILED', 'CANCELLED') AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND result_snapshot IS NULL AND result_sha256 IS NULL AND scenario_spec_snapshot IS NULL "
        "AND scenario_spec_sha256 IS NULL AND trace_snapshot IS NULL AND trace_sha256 IS NULL)"
    )


def upgrade() -> None:
    op.drop_constraint("ck_analysis_runs_state_payload", "analysis_runs", type_="check")
    op.drop_constraint("ck_analysis_runs_versions_nonempty", "analysis_runs", type_="check")
    op.add_column("analysis_runs", sa.Column("run_kind", sa.Text(), server_default=sa.text("'FULL_ANALYSIS'"), nullable=False))
    op.add_column("analysis_runs", sa.Column("trace_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("analysis_runs", sa.Column("trace_sha256", sa.Text(), nullable=True))
    op.add_column("analysis_runs", sa.Column("version_bindings_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("analysis_runs", sa.Column("version_bindings_sha256", sa.Text(), nullable=True))
    op.alter_column("analysis_runs", "economics_version", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint("ck_analysis_runs_kind", "analysis_runs", "run_kind IN ('FULL_ANALYSIS', 'CAPACITY_ANALYSIS')")
    op.create_check_constraint("ck_analysis_runs_trace_object", "analysis_runs", "trace_snapshot IS NULL OR jsonb_typeof(trace_snapshot) = 'object'")
    op.create_check_constraint("ck_analysis_runs_version_bindings_object", "analysis_runs", "version_bindings_snapshot IS NULL OR jsonb_typeof(version_bindings_snapshot) = 'object'")
    op.create_check_constraint("ck_analysis_runs_trace_sha256", "analysis_runs", f"trace_sha256 IS NULL OR trace_sha256 ~ '{SHA}'")
    op.create_check_constraint("ck_analysis_runs_version_bindings_sha256", "analysis_runs", f"version_bindings_sha256 IS NULL OR version_bindings_sha256 ~ '{SHA}'")
    op.create_check_constraint(
        "ck_analysis_runs_versions_nonempty", "analysis_runs",
        "length(btrim(catalog_version_code)) > 0 AND length(btrim(rules_version)) > 0 "
        "AND (economics_version IS NULL OR length(btrim(economics_version)) > 0) "
        "AND length(btrim(object_profile_version)) > 0 AND length(btrim(application_version)) > 0 "
        "AND ((run_kind = 'FULL_ANALYSIS' AND economics_version IS NOT NULL) "
        "OR (run_kind = 'CAPACITY_ANALYSIS' AND economics_version IS NULL "
        "AND version_bindings_snapshot IS NOT NULL AND version_bindings_sha256 IS NOT NULL))",
    )
    op.create_check_constraint("ck_analysis_runs_state_payload", "analysis_runs", _state_constraint())
    op.execute("DROP TRIGGER IF EXISTS trg_analysis_runs_immutable ON analysis_runs")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_analysis_run_immutability()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') THEN
                RAISE EXCEPTION 'terminal analysis run is immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.scenario_id IS DISTINCT FROM OLD.scenario_id
               OR NEW.parent_run_id IS DISTINCT FROM OLD.parent_run_id OR NEW.run_kind IS DISTINCT FROM OLD.run_kind
               OR NEW.input_snapshot IS DISTINCT FROM OLD.input_snapshot OR NEW.input_sha256 IS DISTINCT FROM OLD.input_sha256
               OR NEW.catalog_version_id IS DISTINCT FROM OLD.catalog_version_id
               OR NEW.catalog_version_code IS DISTINCT FROM OLD.catalog_version_code
               OR NEW.rules_version IS DISTINCT FROM OLD.rules_version OR NEW.economics_version IS DISTINCT FROM OLD.economics_version
               OR NEW.object_profile_version IS DISTINCT FROM OLD.object_profile_version
               OR NEW.application_version IS DISTINCT FROM OLD.application_version
               OR NEW.version_bindings_snapshot IS DISTINCT FROM OLD.version_bindings_snapshot
               OR NEW.version_bindings_sha256 IS DISTINCT FROM OLD.version_bindings_sha256
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'analysis run input and version snapshot is immutable' USING ERRCODE = '23514';
            END IF;
            IF NOT ((OLD.status = 'PENDING' AND NEW.status = 'RUNNING') OR
                    (OLD.status = 'RUNNING' AND NEW.status IN ('SUCCEEDED', 'FAILED', 'CANCELLED'))) THEN
                RAISE EXCEPTION 'invalid analysis run transition' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER trg_analysis_runs_immutable BEFORE UPDATE ON analysis_runs "
        "FOR EACH ROW EXECUTE FUNCTION enforce_analysis_run_immutability()"
    )
    op.alter_column("analysis_runs", "run_kind", server_default=None)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_analysis_runs_immutable ON analysis_runs")
    op.execute("DELETE FROM analysis_runs WHERE run_kind = 'CAPACITY_ANALYSIS'")
    op.drop_constraint("ck_analysis_runs_state_payload", "analysis_runs", type_="check")
    op.drop_constraint("ck_analysis_runs_versions_nonempty", "analysis_runs", type_="check")
    for name in ("ck_analysis_runs_version_bindings_sha256", "ck_analysis_runs_trace_sha256", "ck_analysis_runs_version_bindings_object", "ck_analysis_runs_trace_object", "ck_analysis_runs_kind"):
        op.drop_constraint(name, "analysis_runs", type_="check")
    op.alter_column("analysis_runs", "economics_version", existing_type=sa.Text(), nullable=False)
    for column in ("version_bindings_sha256", "version_bindings_snapshot", "trace_sha256", "trace_snapshot", "run_kind"):
        op.drop_column("analysis_runs", column)
    op.create_check_constraint(
        "ck_analysis_runs_versions_nonempty", "analysis_runs",
        "length(btrim(catalog_version_code)) > 0 AND length(btrim(rules_version)) > 0 AND length(btrim(economics_version)) > 0 AND length(btrim(object_profile_version)) > 0 AND length(btrim(application_version)) > 0",
    )
    op.create_check_constraint(
        "ck_analysis_runs_state_payload", "analysis_runs",
        "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL AND result_snapshot IS NULL AND scenario_spec_snapshot IS NULL) OR "
        "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL AND result_snapshot IS NULL AND scenario_spec_snapshot IS NULL) OR "
        "(status = 'SUCCEEDED' AND started_at IS NOT NULL AND finished_at IS NOT NULL AND result_snapshot IS NOT NULL AND result_sha256 IS NOT NULL AND scenario_spec_snapshot IS NOT NULL AND scenario_spec_sha256 IS NOT NULL) OR "
        "(status IN ('FAILED', 'CANCELLED') AND started_at IS NOT NULL AND finished_at IS NOT NULL AND result_snapshot IS NULL AND result_sha256 IS NULL AND scenario_spec_snapshot IS NULL AND scenario_spec_sha256 IS NULL)",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_analysis_run_immutability()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') THEN
                RAISE EXCEPTION 'terminal analysis run is immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.project_id IS DISTINCT FROM OLD.project_id
               OR NEW.scenario_id IS DISTINCT FROM OLD.scenario_id
               OR NEW.parent_run_id IS DISTINCT FROM OLD.parent_run_id
               OR NEW.input_snapshot IS DISTINCT FROM OLD.input_snapshot
               OR NEW.input_sha256 IS DISTINCT FROM OLD.input_sha256
               OR NEW.catalog_version_id IS DISTINCT FROM OLD.catalog_version_id
               OR NEW.catalog_version_code IS DISTINCT FROM OLD.catalog_version_code
               OR NEW.rules_version IS DISTINCT FROM OLD.rules_version
               OR NEW.economics_version IS DISTINCT FROM OLD.economics_version
               OR NEW.object_profile_version IS DISTINCT FROM OLD.object_profile_version
               OR NEW.application_version IS DISTINCT FROM OLD.application_version
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'analysis run input and version snapshot is immutable' USING ERRCODE = '23514';
            END IF;
            IF NOT ((OLD.status = 'PENDING' AND NEW.status = 'RUNNING') OR
                    (OLD.status = 'RUNNING' AND NEW.status IN ('SUCCEEDED', 'FAILED', 'CANCELLED'))) THEN
                RAISE EXCEPTION 'invalid analysis run transition' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER trg_analysis_runs_immutable BEFORE UPDATE ON analysis_runs "
        "FOR EACH ROW EXECUTE FUNCTION enforce_analysis_run_immutability()"
    )
