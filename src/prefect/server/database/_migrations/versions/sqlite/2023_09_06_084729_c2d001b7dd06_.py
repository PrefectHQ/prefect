"""Adds heartbeat_interval_seconds column to worker table

Revision ID: c2d001b7dd06
Revises: 5b0bd3b41a23
Create Date: 2023-09-06 08:47:29.381718

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2d001b7dd06"
down_revision = "5b0bd3b41a23"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("worker", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=True)
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("worker", schema=None) as batch_op:
        batch_op.drop_column("heartbeat_interval_seconds")

    op.execute("PRAGMA foreign_keys=ON")
