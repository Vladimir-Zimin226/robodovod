"""Persist versioned picking work and economics snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0014_picking_project_runs'
down_revision = '0013_operation_batches'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('picking_project_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('picking_project_runs.id', ondelete='CASCADE')),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('input_snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('input_sha256', sa.Text(), nullable=False),
        sa.Column('result_snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('result_sha256', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(input_snapshot) = 'object'", name='ck_picking_runs_input'),
        sa.CheckConstraint("jsonb_typeof(result_snapshot) = 'object'", name='ck_picking_runs_result'),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name='ck_picking_runs_input_sha256'),
        sa.CheckConstraint("result_sha256 ~ '^[0-9a-f]{64}$'", name='ck_picking_runs_result_sha256'),
        sa.CheckConstraint("status IN ('COMPLETE', 'PARTIAL')", name='ck_picking_runs_status'))
    op.create_index('ix_picking_runs_project_created', 'picking_project_runs', ['project_id', 'created_at'])
    op.execute("""CREATE FUNCTION protect_picking_project_run() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'picking project run is immutable'; END;
    $$ LANGUAGE plpgsql;""")
    op.execute("""CREATE TRIGGER picking_project_run_guard BEFORE UPDATE ON picking_project_runs
    FOR EACH ROW EXECUTE FUNCTION protect_picking_project_run();""")


def downgrade():
    op.execute('DROP TRIGGER picking_project_run_guard ON picking_project_runs')
    op.execute('DROP FUNCTION protect_picking_project_run()')
    op.drop_index('ix_picking_runs_project_created', table_name='picking_project_runs')
    op.drop_table('picking_project_runs')
