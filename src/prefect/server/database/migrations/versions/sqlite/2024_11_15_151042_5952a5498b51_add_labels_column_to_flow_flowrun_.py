"""Add `labels` column to Flow, FlowRun, TaskRun, and Deployment

Revision ID: 5952a5498b51
Revises: 4ad4658cbefe
Create Date: 2024-11-15 15:10:42.138653

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "5952a5498b51"
down_revision = "4ad4658cbefe"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "labels",
                prefect.server.utilities.database.JSON(astext_type=sa.Text()),
                nullable=True,
            )
        )

    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "labels",
                prefect.server.utilities.database.JSON(astext_type=sa.Text()),
                nullable=True,
            )
        )

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "labels",
                prefect.server.utilities.database.JSON(astext_type=sa.Text()),
                nullable=True,
            )
        )

    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "labels",
                prefect.server.utilities.database.JSON(astext_type=sa.Text()),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_column("labels")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("labels")

    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_column("labels")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("labels")
