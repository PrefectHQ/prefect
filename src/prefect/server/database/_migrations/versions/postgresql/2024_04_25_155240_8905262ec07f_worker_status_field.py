"""Worker status field

Revision ID: 8905262ec07f
Revises: 7ae9e431e67a
Create Date: 2024-04-25 15:52:40.235822

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from prefect.server.utilities.database import UUID, Timestamp

# revision identifiers, used by Alembic.
revision = "8905262ec07f"
down_revision = "7ae9e431e67a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "work_pool",
        sa.Column(
            "last_transitioned_status_at", Timestamp(timezone=True), nullable=True
        ),
    )
    op.add_column("work_pool", sa.Column("last_status_event_id", UUID(), nullable=True))

    worker_status = postgresql.ENUM("ONLINE", "OFFLINE", name="worker_status")
    worker_status.create(op.get_bind())

    op.add_column(
        "worker",
        sa.Column("status", worker_status, server_default="OFFLINE", nullable=False),
    )


def downgrade():
    op.drop_column("worker", "status")

    op.drop_column("work_pool", "last_transitioned_status_at")
    op.drop_column("work_pool", "last_status_event_id")
