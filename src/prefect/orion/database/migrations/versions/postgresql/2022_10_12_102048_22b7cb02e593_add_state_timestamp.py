"""Add state_timestamp

Revision ID: 22b7cb02e593
Revises: 2d5e000696f1
Create Date: 2022-10-12 10:20:48.760447

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "22b7cb02e593"
down_revision = "2d5e000696f1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "state_timestamp",
                prefect.orion.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )

    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "state_timestamp",
                prefect.orion.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_column("state_timestamp")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("state_timestamp")
