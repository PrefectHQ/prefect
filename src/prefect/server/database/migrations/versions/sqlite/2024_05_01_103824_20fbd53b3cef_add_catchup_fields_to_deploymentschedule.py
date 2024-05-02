"""add catchup fields to DeploymentSchedule

Revision ID: 20fbd53b3cef
Revises: a8e62d4c72cf
Create Date: 2024-05-01 10:38:24.336255

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20fbd53b3cef"
down_revision = "a8e62d4c72cf"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_active_runs", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("max_scheduled_runs", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("catchup", sa.Boolean(), server_default="0", nullable=False)
        )


def downgrade():
    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.drop_column("catchup")
        batch_op.drop_column("max_scheduled_runs")
        batch_op.drop_column("max_active_runs")
