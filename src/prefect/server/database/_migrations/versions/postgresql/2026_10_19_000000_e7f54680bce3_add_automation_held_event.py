"""Add automation_held_event table

Revision ID: e7f54680bce3
Revises: d4a7e1c93f52
Create Date: 2026-10-19 00:00:00.000000

Holds `expect` events of proactive triggers with `after` that are evaluated before
any bucket exists for their key, so the bucket that opens later can count them.
"""

import sqlalchemy as sa
from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "e7f54680bce3"
down_revision = "d4a7e1c93f52"
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
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
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
    op.create_index(
        "uq_automation_held_event__trigger_key_event",
        "automation_held_event",
        ["automation_id", "trigger_id", "bucketing_key", "event_id"],
        unique=True,
    )
    op.create_index(
        "ix_automation_held_event__trigger_key_occurred",
        "automation_held_event",
        ["automation_id", "trigger_id", "bucketing_key", "occurred", "event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automation_held_event__updated"),
        "automation_held_event",
        ["updated"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_automation_held_event__updated"), table_name="automation_held_event"
    )
    op.drop_index(
        "ix_automation_held_event__trigger_key_occurred",
        table_name="automation_held_event",
    )
    op.drop_index(
        "uq_automation_held_event__trigger_key_event",
        table_name="automation_held_event",
    )
    op.drop_table("automation_held_event")
