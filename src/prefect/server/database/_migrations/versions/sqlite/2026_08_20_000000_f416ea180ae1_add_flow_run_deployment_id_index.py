"""Add index on flow_run(deployment_id)

Revision ID: f416ea180ae1
Revises: 14806cb26270
Create Date: 2026-08-20 00:00:00.000000

Filtering flow runs by deployment (for example the deployment Runs tab, which
calls `POST /api/flow_runs/paginate` with a `deployments.id.any_` filter)
compiles to an equality predicate on `flow_run.deployment_id`. The only
remaining indexes that lead with that column are partial and scheduler-scoped
(`WHERE state_type = 'SCHEDULED'`), so an all-states query scans the whole
table for both the results query and the pagination COUNT. On large tables
this exceeds the database timeout and the API returns a 500.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f416ea180ae1"
down_revision = "14806cb26270"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_flow_run__deployment_id
        ON flow_run (deployment_id)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_flow_run__deployment_id")
