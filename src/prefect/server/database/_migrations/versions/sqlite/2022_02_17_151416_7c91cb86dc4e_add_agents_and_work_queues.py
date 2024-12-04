"""Add agents and work queues

Revision ID: 7c91cb86dc4e
Revises: 619bea85701a
Create Date: 2022-02-17 15:14:16.697816

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "7c91cb86dc4e"
down_revision = "619bea85701a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_queue",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n       "
                " || lower(hex(randomblob(2))) \n        || '-4' \n        ||"
                " substr(lower(hex(randomblob(2))),2) \n        || '-' \n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1) \n        ||"
                " substr(lower(hex(randomblob(2))),2) \n        || '-' \n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "filter",
            prefect.server.utilities.database.Pydantic(
                prefect.server.schemas.core.QueueFilter
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
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n       "
                " || lower(hex(randomblob(2))) \n        || '-4' \n        ||"
                " substr(lower(hex(randomblob(2))),2) \n        || '-' \n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1) \n        ||"
                " substr(lower(hex(randomblob(2))),2) \n        || '-' \n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_activity_time",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "work_queue_id", prefect.server.utilities.database.UUID(), nullable=False
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
