"""add catchup fields to DeploymentSchedule

Revision ID: b23c83a12cb4
Revises: 8905262ec07f
Create Date: 2024-05-01 10:54:01.271642

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b23c83a12cb4"
down_revision = "8905262ec07f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment_schedule", sa.Column("max_active_runs", sa.Integer(), nullable=True)
    )
    op.add_column(
        "deployment_schedule",
        sa.Column("max_scheduled_runs", sa.Integer(), nullable=True),
    )
    op.add_column(
        "deployment_schedule",
        sa.Column("catchup", sa.Boolean(), server_default="0", nullable=False),
    )


def downgrade():
    op.drop_column("deployment_schedule", "catchup")
    op.drop_column("deployment_schedule", "max_scheduled_runs")
    op.drop_column("deployment_schedule", "max_active_runs")
