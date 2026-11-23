"""Add worker ID to logs.

Revision ID: 80b8c25269b8
Revises: 27d8f4e1a6c9
Create Date: 2026-11-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

from prefect.server.utilities.database import UUID

revision = "80b8c25269b8"
down_revision = "27d8f4e1a6c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("log", sa.Column("worker_id", UUID(), nullable=True))


def downgrade():
    with op.batch_alter_table("log") as batch_op:
        batch_op.drop_column("worker_id")
