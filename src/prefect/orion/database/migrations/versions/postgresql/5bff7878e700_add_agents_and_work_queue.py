"""Add agents and work queue

Revision ID: 5bff7878e700
Revises: 5f376def75c3
Create Date: 2022-02-17 14:08:21.839817

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "5bff7878e700"
down_revision = "5f376def75c3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_queue",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "filter",
            prefect.orion.utilities.database.Pydantic(
                prefect.orion.schemas.core.QueueFilter
            ),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_queue")),
        sa.UniqueConstraint("name", name=op.f("uq_work_queue__name")),
    )
    op.create_index(
        op.f("ix_work_queue__updated"), "work_queue", ["updated"], unique=False
    )
    op.create_table(
        "agent",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_activity_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "work_queue_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_queue_id"],
            ["work_queue.id"],
            name=op.f("fk_agent__work_queue_id__work_queue"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent")),
        sa.UniqueConstraint("name", name=op.f("uq_agent__name")),
    )
    op.create_index(op.f("ix_agent__updated"), "agent", ["updated"], unique=False)
    op.create_index(
        op.f("ix_agent__work_queue_id"), "agent", ["work_queue_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_agent__work_queue_id"), table_name="agent")
    op.drop_index(op.f("ix_agent__updated"), table_name="agent")
    op.drop_table("agent")
    op.drop_index(op.f("ix_work_queue__updated"), table_name="work_queue")
    op.drop_table("work_queue")
