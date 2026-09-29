"""Immutable snapshots of multi-operation project inventories."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0013_operation_batches'
down_revision = '0012_admin_catalog'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('operation_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('input_revision', sa.Text(), nullable=False),
        sa.Column('snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('snapshot_sha256', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(snapshot) = 'object'", name='ck_operation_batches_snapshot'),
        sa.CheckConstraint("snapshot_sha256 ~ '^[0-9a-f]{64}$'", name='ck_operation_batches_sha256'),
        sa.CheckConstraint("length(btrim(input_revision)) > 0", name='ck_operation_batches_revision'))
    op.create_index('ix_operation_batches_project_created', 'operation_batches', ['project_id', 'created_at'])
    op.execute("""CREATE FUNCTION protect_operation_batch() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'operation batch snapshot is immutable'; END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER operation_batch_guard BEFORE UPDATE ON operation_batches
    FOR EACH ROW EXECUTE FUNCTION protect_operation_batch();""")


def downgrade():
    op.execute('DROP TRIGGER operation_batch_guard ON operation_batches')
    op.execute('DROP FUNCTION protect_operation_batch()')
    op.drop_index('ix_operation_batches_project_created', table_name='operation_batches')
    op.drop_table('operation_batches')
