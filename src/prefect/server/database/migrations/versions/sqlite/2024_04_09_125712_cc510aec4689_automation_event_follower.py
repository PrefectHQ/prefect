"""Automation event follower

Revision ID: cc510aec4689
Revises: 8644a9595a08
Create Date: 2024-04-09 12:57:12.420482

"""

import sqlalchemy as sa
from alembic import op

import prefect
import prefect.server.utilities.database
from prefect.server.events.schemas.events import ReceivedEvent

# revision identifiers, used by Alembic.
revision = "cc510aec4689"
down_revision = "8644a9595a08"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation_event_follower",
        sa.Column(
            "leader_event_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "follower_event_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.Column(
            "received",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "follower",
            prefect.server.utilities.database.Pydantic(ReceivedEvent),
            nullable=False,
        ),
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_event_follower")),
        sa.UniqueConstraint(
            "follower_event_id",
            name=op.f("uq_automation_event_follower__follower_event_id"),
        ),
    )
    with op.batch_alter_table("automation_event_follower", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_automation_event_follower__leader_event_id"),
            ["leader_event_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_automation_event_follower__received"),
            ["received"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_automation_event_follower__updated"),
            ["updated"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("automation_event_follower", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_automation_event_follower__updated"))
        batch_op.drop_index(batch_op.f("ix_automation_event_follower__received"))
        batch_op.drop_index(batch_op.f("ix_automation_event_follower__leader_event_id"))

    op.drop_table("automation_event_follower")
