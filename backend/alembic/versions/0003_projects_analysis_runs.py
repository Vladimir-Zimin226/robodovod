"""add users, projects, scenarios and immutable analysis runs

Revision ID: 0003_projects_analysis_runs
Revises: 0002_catalog_domain
Create Date: 2026-09-16 22:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_projects_analysis_runs"
down_revision: Union[str, None] = "0002_catalog_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email_normalized", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default=sa.text("'USER'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email_normalized)) AND length(email_normalized) BETWEEN 3 AND 320 AND position('@' in email_normalized) > 1",
            name="ck_users_email_normalized",
        ),
        sa.CheckConstraint("length(password_hash) > 0", name="ck_users_password_hash"),
        sa.CheckConstraint(
            "name IS NULL OR (name = btrim(name) AND length(name) BETWEEN 1 AND 200)",
            name="ck_users_name",
        ),
        sa.CheckConstraint("role IN ('USER', 'ADMIN')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_users_status"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_users_timestamp_order"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_sha256", sa.Text(), nullable=False),
        sa.Column("csrf_sha256", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("token_sha256 ~ '^[0-9a-f]{64}$'", name="ck_user_sessions_token_sha256"),
        sa.CheckConstraint("csrf_sha256 ~ '^[0-9a-f]{64}$'", name="ck_user_sessions_csrf_sha256"),
        sa.CheckConstraint("expires_at > created_at", name="ck_user_sessions_expiry"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_sha256", name="uq_user_sessions_token_sha256"),
    )
    op.create_index("ix_user_sessions_user_expires", "user_sessions", ["user_id", "expires_at"])

    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("copied_from_project_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("name = btrim(name) AND length(name) BETWEEN 1 AND 200", name="ck_projects_name"),
        sa.CheckConstraint("description IS NULL OR length(description) <= 4000", name="ck_projects_description"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DELETING', 'DELETE_FAILED')", name="ck_projects_status"),
        sa.CheckConstraint("jsonb_typeof(profile) = 'object'", name="ck_projects_profile_object"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_projects_timestamp_order"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_updated", "projects", ["owner_id", "updated_at"])

    op.create_table(
        "project_deletion_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_subject_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("storage_keys", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'FAILED', 'SUCCEEDED')", name="ck_project_deletion_jobs_status"),
        sa.CheckConstraint("jsonb_typeof(storage_keys) = 'array'", name="ck_project_deletion_jobs_keys"),
        sa.CheckConstraint("attempts >= 0", name="ck_project_deletion_jobs_attempts"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_subject_id", name="uq_project_deletion_jobs_project"),
    )

    op.create_table(
        "project_files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(btrim(original_name)) > 0", name="ck_project_files_name"),
        sa.CheckConstraint("length(btrim(media_type)) > 0", name="ck_project_files_media_type"),
        sa.CheckConstraint("byte_size > 0", name="ck_project_files_byte_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_project_files_sha256"),
        sa.CheckConstraint("storage_key = btrim(storage_key) AND length(storage_key) > 0", name="ck_project_files_storage_key"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_project_files_storage_key"),
    )
    op.create_index("ix_project_files_project", "project_files", ["project_id"])

    op.create_table(
        "scenarios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("slot IN ('BASE', 'OPTIMISTIC', 'PESSIMISTIC')", name="ck_scenarios_slot"),
        sa.CheckConstraint("name = btrim(name) AND length(name) BETWEEN 1 AND 120", name="ck_scenarios_name"),
        sa.CheckConstraint("jsonb_typeof(inputs) = 'object'", name="ck_scenarios_inputs_object"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_scenarios_timestamp_order"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slot", name="uq_scenarios_project_slot"),
    )
    op.create_index("ix_scenarios_project", "scenarios", ["project_id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("scenario_id", sa.UUID(), nullable=True),
        sa.Column("parent_run_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_sha256", sa.Text(), nullable=False),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_sha256", sa.Text(), nullable=True),
        sa.Column("scenario_spec_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scenario_spec_sha256", sa.Text(), nullable=True),
        sa.Column("revision_id", sa.Text(), nullable=True),
        sa.Column("catalog_version_id", sa.UUID(), nullable=True),
        sa.Column("catalog_version_code", sa.Text(), nullable=False),
        sa.Column("rules_version", sa.Text(), nullable=False),
        sa.Column("economics_version", sa.Text(), nullable=False),
        sa.Column("object_profile_version", sa.Text(), nullable=False),
        sa.Column("application_version", sa.Text(), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')", name="ck_analysis_runs_status"),
        sa.CheckConstraint("jsonb_typeof(input_snapshot) = 'object'", name="ck_analysis_runs_input_object"),
        sa.CheckConstraint("result_snapshot IS NULL OR jsonb_typeof(result_snapshot) = 'object'", name="ck_analysis_runs_result_object"),
        sa.CheckConstraint("scenario_spec_snapshot IS NULL OR jsonb_typeof(scenario_spec_snapshot) = 'object'", name="ck_analysis_runs_scenario_spec_object"),
        sa.CheckConstraint("jsonb_typeof(diagnostics) = 'object'", name="ck_analysis_runs_diagnostics_object"),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="ck_analysis_runs_input_sha256"),
        sa.CheckConstraint("result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$'", name="ck_analysis_runs_result_sha256"),
        sa.CheckConstraint("scenario_spec_sha256 IS NULL OR scenario_spec_sha256 ~ '^[0-9a-f]{64}$'", name="ck_analysis_runs_scenario_spec_sha256"),
        sa.CheckConstraint(
            "length(btrim(catalog_version_code)) > 0 AND length(btrim(rules_version)) > 0 AND length(btrim(economics_version)) > 0 AND length(btrim(object_profile_version)) > 0 AND length(btrim(application_version)) > 0",
            name="ck_analysis_runs_versions_nonempty",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL AND result_snapshot IS NULL AND scenario_spec_snapshot IS NULL) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL AND result_snapshot IS NULL AND scenario_spec_snapshot IS NULL) OR "
            "(status = 'SUCCEEDED' AND started_at IS NOT NULL AND finished_at IS NOT NULL AND result_snapshot IS NOT NULL AND result_sha256 IS NOT NULL AND scenario_spec_snapshot IS NOT NULL AND scenario_spec_sha256 IS NOT NULL) OR "
            "(status IN ('FAILED', 'CANCELLED') AND started_at IS NOT NULL AND finished_at IS NOT NULL AND result_snapshot IS NULL AND result_sha256 IS NULL AND scenario_spec_snapshot IS NULL AND scenario_spec_sha256 IS NULL)",
            name="ck_analysis_runs_state_payload",
        ),
        sa.CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="ck_analysis_runs_timestamp_order"),
        sa.ForeignKeyConstraint(["catalog_version_id"], ["catalog_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_runs_project_created", "analysis_runs", ["project_id", "created_at"])

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("subject_user_id", sa.UUID(), nullable=True),
        sa.Column("project_subject_id", sa.UUID(), nullable=True),
        sa.Column("aggregate", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("event_type = btrim(event_type) AND length(event_type) BETWEEN 1 AND 100", name="ck_audit_entries_event_type"),
        sa.CheckConstraint("jsonb_typeof(aggregate) = 'object'", name="ck_audit_entries_aggregate"),
        sa.CheckConstraint("retention_until IS NULL OR retention_until >= created_at", name="ck_audit_entries_retention"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_entries_project", "audit_entries", ["project_subject_id"])
    op.create_index("ix_audit_entries_retention", "audit_entries", ["retention_until"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_last_active_admin_change()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.role = 'ADMIN' AND OLD.status = 'ACTIVE'
               AND (TG_OP = 'DELETE' OR NEW.role <> 'ADMIN' OR NEW.status <> 'ACTIVE') THEN
                PERFORM pg_advisory_xact_lock(hashtext('robodovod-active-admin'));
                IF NOT EXISTS (
                    SELECT 1 FROM users
                    WHERE role = 'ADMIN' AND status = 'ACTIVE' AND id <> OLD.id
                ) THEN
                    RAISE EXCEPTION 'cannot remove the last active admin'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_keep_last_active_admin
        BEFORE UPDATE OF role, status OR DELETE ON users
        FOR EACH ROW EXECUTE FUNCTION prevent_last_active_admin_change();
        """
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
                RAISE EXCEPTION 'analysis run input and version snapshot is immutable'
                    USING ERRCODE = '23514';
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
        """
        CREATE TRIGGER trg_analysis_runs_immutable
        BEFORE UPDATE ON analysis_runs
        FOR EACH ROW EXECUTE FUNCTION enforce_analysis_run_immutability();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_analysis_runs_immutable ON analysis_runs")
    op.execute("DROP FUNCTION IF EXISTS enforce_analysis_run_immutability()")
    op.execute("DROP TRIGGER IF EXISTS trg_users_keep_last_active_admin ON users")
    op.execute("DROP FUNCTION IF EXISTS prevent_last_active_admin_change()")
    op.drop_index("ix_audit_entries_retention", table_name="audit_entries")
    op.drop_index("ix_audit_entries_project", table_name="audit_entries")
    op.drop_table("audit_entries")
    op.drop_index("ix_analysis_runs_project_created", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index("ix_scenarios_project", table_name="scenarios")
    op.drop_table("scenarios")
    op.drop_index("ix_project_files_project", table_name="project_files")
    op.drop_table("project_files")
    op.drop_table("project_deletion_jobs")
    op.drop_index("ix_projects_owner_updated", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_user_sessions_user_expires", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("users")
