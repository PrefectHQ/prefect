"""Worker status field

Revision ID: a8e62d4c72cf
Revises: 75c8f17b8b51
Create Date: 2024-04-25 15:51:20.234353

"""

import sqlalchemy as sa
from alembic import op

from prefect.server.utilities.database import UUID, Timestamp

# revision identifiers, used by Alembic.
revision = "a8e62d4c72cf"
down_revision = "75c8f17b8b51"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "last_transitioned_status_at", Timestamp(timezone=True), nullable=True
            ),
        )
        batch_op.add_column(sa.Column("last_status_event_id", UUID(), nullable=True))

    with op.batch_alter_table("worker", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum("ONLINE", "OFFLINE", name="worker_status"),
                server_default="OFFLINE",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("worker", schema=None) as batch_op:
        batch_op.drop_column("status")

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_column("last_transitioned_status_at")
        batch_op.drop_column("last_status_event_id")
