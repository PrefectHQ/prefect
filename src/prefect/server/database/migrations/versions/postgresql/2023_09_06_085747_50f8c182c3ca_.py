"""Adds heartbeat_interval_seconds column to worker table

Revision ID: 50f8c182c3ca
Revises: 5f623ddbf7fe
Create Date: 2023-09-06 08:57:47.166983

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "50f8c182c3ca"
down_revision = "5f623ddbf7fe"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "worker", sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column("worker", "heartbeat_interval_seconds")
