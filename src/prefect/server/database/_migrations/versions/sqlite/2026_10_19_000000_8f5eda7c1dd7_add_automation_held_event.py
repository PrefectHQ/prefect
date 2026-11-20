"""Add automation_held_event table

Revision ID: 8f5eda7c1dd7
Revises: a3b9c7d2e5f1
Create Date: 2026-10-19 00:00:00.000000

Holds `expect` events of proactive triggers with `after` that are evaluated before
any bucket exists for their key, so the bucket that opens later can count them.
"""

import sqlalchemy as sa
from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "8f5eda7c1dd7"
down_revision = "a3b9c7d2e5f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation_held_event",
        sa.Column(
            "automation_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "trigger_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "bucketing_key",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("event_id", prefect.server.utilities.database.UUID(), nullable=False),
        sa.Column(
            "occurred",
            prefect.server.utilities.database.Timestamp(timezone=True),
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
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name=op.f("fk_automation_held_event__automation_id__automation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_held_event")),
    )
    with op.batch_alter_table("automation_held_event", schema=None) as batch_op:
        batch_op.create_index(
            "uq_automation_held_event__trigger_key_event",
            ["automation_id", "trigger_id", "bucketing_key", "event_id"],
            unique=True,
        )
        batch_op.create_index(
            "ix_automation_held_event__trigger_key_occurred",
            ["automation_id", "trigger_id", "bucketing_key", "occurred", "event_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_automation_held_event__updated"),
            ["updated"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("automation_held_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_automation_held_event__updated"))
        batch_op.drop_index("ix_automation_held_event__trigger_key_occurred")
        batch_op.drop_index("uq_automation_held_event__trigger_key_event")

    op.drop_table("automation_held_event")
