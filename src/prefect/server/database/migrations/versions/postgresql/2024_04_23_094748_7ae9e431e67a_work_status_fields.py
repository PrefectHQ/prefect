"""Work status fields

Revision ID: 7ae9e431e67a
Revises: 15768c2ec702
Create Date: 2024-04-23 09:47:48.344011

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7ae9e431e67a"
down_revision = "15768c2ec702"
branch_labels = None
depends_on = None


def upgrade():
    deployment_status = postgresql.ENUM("READY", "NOT_READY", name="deployment_status")
    deployment_status.create(op.get_bind())

    op.add_column(
        "deployment",
        sa.Column(
            "status",
            deployment_status,
            nullable=False,
            server_default="NOT_READY",
        ),
    )

    work_pool_status = postgresql.ENUM(
        "READY", "NOT_READY", "PAUSED", name="work_pool_status"
    )
    work_pool_status.create(op.get_bind())

    op.add_column(
        "work_pool",
        sa.Column(
            "status",
            work_pool_status,
            nullable=False,
            server_default="NOT_READY",
        ),
    )

    work_queue_status = postgresql.ENUM(
        "READY", "NOT_READY", "PAUSED", name="work_queue_status"
    )
    work_queue_status.create(op.get_bind())

    op.add_column(
        "work_queue",
        sa.Column(
            "status",
            work_queue_status,
            nullable=False,
            server_default="NOT_READY",
        ),
    )


def downgrade():
    op.drop_column("work_queue", "status")
    op.drop_column("work_pool", "status")
    op.drop_column("deployment", "status")

    op.execute("DROP TYPE work_queue_status")
    op.execute("DROP TYPE work_pool_status")
    op.execute("DROP TYPE deployment_status")
