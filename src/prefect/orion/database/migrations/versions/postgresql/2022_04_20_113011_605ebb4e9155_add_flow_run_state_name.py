"""Add flow_run.state_name

Revision ID: 605ebb4e9155
Revises: 2e7e1428ffce
Create Date: 2022-04-20 11:30:11.934795

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "605ebb4e9155"
down_revision = "2e7e1428ffce"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow_run", sa.Column("state_name", sa.String(), nullable=True))
    op.add_column("task_run", sa.Column("state_name", sa.String(), nullable=True))

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_flow_run__state_name
            ON flow_run(state_name)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_task_run__state_name
            ON task_run(state_name)
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_flow_run__state_name")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_task_run__state_name")
    op.drop_column("flow_run", "state_name")
    op.drop_column("task_run", "state_name")
