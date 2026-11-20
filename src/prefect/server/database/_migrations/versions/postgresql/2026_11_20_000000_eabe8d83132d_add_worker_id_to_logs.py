"""Add worker ID to logs.

Revision ID: eabe8d83132d
Revises: 91e2b8f3d6a4
Create Date: 2026-11-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

from prefect.server.utilities.database import UUID

revision = "eabe8d83132d"
down_revision = "91e2b8f3d6a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("log", sa.Column("worker_id", UUID(), nullable=True))


def downgrade():
    op.drop_column("log", "worker_id")
