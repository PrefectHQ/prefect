"""Add index for scheduled deployments

Revision ID: a0284438370e
Revises: af52717cf201
Create Date: 2022-11-05 18:06:19.568896

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a0284438370e"
down_revision = "af52717cf201"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX ix_flow_run__scheduler_deployment_id_auto_scheduled_next_scheduled_start_time 
        ON flow_run (deployment_id, auto_scheduled, next_scheduled_start_time) 
        WHERE state_type = 'SCHEDULED';
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX ix_flow_run__scheduler_deployment_id_auto_scheduled_next_scheduled_start_time;
        """
    )
