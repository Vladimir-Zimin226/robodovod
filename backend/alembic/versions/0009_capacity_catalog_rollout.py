"""Persist capacity rollout approval and rollback binding.

Revision ID: 0009_capacity_catalog_rollout
Revises: 0008_capacity_snapshots
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_capacity_catalog_rollout"
down_revision: str | None = "0008_capacity_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHA = "^[0-9a-f]{64}$"


def upgrade() -> None:
    op.add_column("catalog_activations", sa.Column("rollout_policy_version", sa.Text(), nullable=True))
    op.add_column("catalog_activations", sa.Column("approval_report_sha256", sa.Text(), nullable=True))
    op.add_column("catalog_activations", sa.Column("rollback_mode", sa.Text(), nullable=True))
    op.add_column(
        "catalog_activations",
        sa.Column("rollback_catalog_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_catalog_activations_rollback_catalog_version_id",
        "catalog_activations", "catalog_versions",
        ["rollback_catalog_version_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_catalog_activations_approval_sha256", "catalog_activations",
        f"approval_report_sha256 IS NULL OR approval_report_sha256 ~ '{SHA}'",
    )
    op.create_check_constraint(
        "ck_catalog_activations_capacity_approval", "catalog_activations",
        "(slot = 'capacity' AND rollout_policy_version IS NOT NULL "
        "AND approval_report_sha256 IS NOT NULL "
        "AND rollback_mode IN ('DEACTIVATE', 'RESTORE_VERSION') "
        "AND ((rollback_mode = 'DEACTIVATE' AND rollback_catalog_version_id IS NULL) "
        "OR (rollback_mode = 'RESTORE_VERSION' AND rollback_catalog_version_id IS NOT NULL))) OR "
        "(slot <> 'capacity' AND rollout_policy_version IS NULL "
        "AND approval_report_sha256 IS NULL AND rollback_mode IS NULL "
        "AND rollback_catalog_version_id IS NULL)",
    )


def downgrade() -> None:
    # Never erase rollout history implicitly. Operators must explicitly restore
    # or archive capacity activations before downgrading this contract.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM catalog_activations WHERE slot = 'capacity') THEN "
        "RAISE EXCEPTION 'cannot downgrade while capacity activation history exists'; "
        "END IF; END $$"
    )
    op.drop_constraint("ck_catalog_activations_capacity_approval", "catalog_activations", type_="check")
    op.drop_constraint("ck_catalog_activations_approval_sha256", "catalog_activations", type_="check")
    op.drop_constraint(
        "fk_catalog_activations_rollback_catalog_version_id",
        "catalog_activations", type_="foreignkey",
    )
    op.drop_column("catalog_activations", "rollback_catalog_version_id")
    op.drop_column("catalog_activations", "rollback_mode")
    op.drop_column("catalog_activations", "approval_report_sha256")
    op.drop_column("catalog_activations", "rollout_policy_version")
