"""add job config to flow run

Revision ID: 512343402e7d
Revises: f93e1439f022
Create Date: 2024-08-21 11:25:02.594239

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "512343402e7d"
down_revision = "f93e1439f022"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "job_configuration",
                prefect.server.utilities.database.JSON(astext_type=sa.Text()),
                server_default="{}",
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("job_configuration")
