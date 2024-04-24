"""Work status fields

Revision ID: 75c8f17b8b51
Revises: 824e9edafa60
Create Date: 2024-04-23 09:47:01.931872

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "75c8f17b8b51"
down_revision = "824e9edafa60"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum("READY", "NOT_READY", name="deployment_status"),
                nullable=False,
                server_default="NOT_READY",
            )
        )

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum("READY", "NOT_READY", "PAUSED", name="work_pool_status"),
                nullable=False,
                server_default="NOT_READY",
            )
        )

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum("READY", "NOT_READY", "PAUSED", name="work_queue_status"),
                nullable=False,
                server_default="NOT_READY",
            )
        )


def downgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_column("status")

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_column("status")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("status")
