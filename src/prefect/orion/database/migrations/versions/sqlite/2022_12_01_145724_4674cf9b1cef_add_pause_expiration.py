"""Adds pause expiration metadata to flow runs

Revision ID: 4674cf9b1cef
Revises: 7201de756d85
Create Date: 2022-12-01 14:57:24.639963

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "4674cf9b1cef"
down_revision = "7201de756d85"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "pause_expiration_time",
                prefect.orion.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("pause_expiration_time")
