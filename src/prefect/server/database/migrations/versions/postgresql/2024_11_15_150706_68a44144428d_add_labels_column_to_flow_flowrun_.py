"""Add `labels` column to Flow, FlowRun, TaskRun, and Deployment

Revision ID: 68a44144428d
Revises: eaec5004771f
Create Date: 2024-11-15 15:07:06.141947
"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "68a44144428d"
down_revision = "eaec5004771f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column(
            "labels",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "flow",
        sa.Column(
            "labels",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "flow_run",
        sa.Column(
            "labels",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "task_run",
        sa.Column(
            "labels",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("task_run", "labels")
    op.drop_column("flow_run", "labels")
    op.drop_column("flow", "labels")
    op.drop_column("deployment", "labels")
