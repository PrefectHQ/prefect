"""Add index for scheduled deployments

Revision ID: 54c1876c68ae
Revises: 41e5ed9e1034
Create Date: 2022-11-05 18:05:55.050650

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "54c1876c68ae"
down_revision = "41e5ed9e1034"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY ix_flow_run__scheduler_deployment_id_auto_scheduled_next_scheduled_start_time 
            ON flow_run (deployment_id, auto_scheduled, next_scheduled_start_time) 
            WHERE state_type = 'SCHEDULED';
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY ix_flow_run__scheduler_deployment_id_auto_scheduled_next_scheduled_start_time;
            """
        )
