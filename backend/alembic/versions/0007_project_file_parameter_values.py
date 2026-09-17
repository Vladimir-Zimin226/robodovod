"""Preserve every validated project-file profile parameter.

Revision ID: 0007_file_parameter_values
Revises: 0006_project_file_intake
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_file_parameter_values"
down_revision: str | None = "0006_project_file_intake"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_file_imports",
        sa.Column(
            "parameter_values",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "project_file_imports",
        sa.Column(
            "parameter_provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_project_file_imports_values_object",
        "project_file_imports",
        "jsonb_typeof(parameter_values) = 'object'",
    )
    op.create_check_constraint(
        "ck_project_file_imports_parameter_provenance_object",
        "project_file_imports",
        "jsonb_typeof(parameter_provenance) = 'object'",
    )
    op.alter_column("project_file_imports", "parameter_values", server_default=None)
    op.alter_column("project_file_imports", "parameter_provenance", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_project_file_imports_parameter_provenance_object",
        "project_file_imports",
        type_="check",
    )
    op.drop_constraint(
        "ck_project_file_imports_values_object", "project_file_imports", type_="check"
    )
    op.drop_column("project_file_imports", "parameter_provenance")
    op.drop_column("project_file_imports", "parameter_values")
