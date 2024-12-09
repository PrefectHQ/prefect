"""Add events and event_resources tables

Revision ID: 15768c2ec702
Revises: 954db7517015
Create Date: 2024-04-10 19:47:42.208099

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text

import prefect

# revision identifiers, used by Alembic.
revision = "15768c2ec702"
down_revision = "954db7517015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "event_resources",
        sa.Column(
            "occurred",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("resource_role", sa.Text(), nullable=False),
        sa.Column("resource", sa.JSON(), nullable=False),
        sa.Column("event_id", prefect.server.utilities.database.UUID(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_resources")),
    )
    op.create_index(
        "ix_event_resources__resource_id__occurred",
        "event_resources",
        ["resource_id", "occurred"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_resources__updated"),
        "event_resources",
        ["updated"],
        unique=False,
    )
    op.create_table(
        "events",
        sa.Column(
            "occurred",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column(
            "resource",
            prefect.server.utilities.database.JSON(astext_type=Text()),
            nullable=False,
        ),
        sa.Column(
            "related_resource_ids",
            prefect.server.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "related",
            prefect.server.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "payload",
            prefect.server.utilities.database.JSON(astext_type=Text()),
            nullable=False,
        ),
        sa.Column(
            "received",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "recorded",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column("follows", prefect.server.utilities.database.UUID(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index("ix_events__event__id", "events", ["event", "id"], unique=False)
    op.create_index(
        "ix_events__event_occurred_id",
        "events",
        ["event", "occurred", "id"],
        unique=False,
    )
    op.create_index(
        "ix_events__event_related_occurred",
        "events",
        ["event", "related", "occurred"],
        unique=False,
    )
    op.create_index(
        "ix_events__event_resource_id_occurred",
        "events",
        ["event", "resource_id", "occurred"],
        unique=False,
    )
    op.create_index("ix_events__occurred", "events", ["occurred"], unique=False)
    op.create_index(
        "ix_events__occurred_id", "events", ["occurred", "id"], unique=False
    )
    op.create_index(
        "ix_events__related_resource_ids",
        "events",
        ["related_resource_ids"],
        unique=False,
    )
    op.create_index(op.f("ix_events__updated"), "events", ["updated"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_events__updated"), table_name="events")
    op.drop_index("ix_events__related_resource_ids", table_name="events")
    op.drop_index("ix_events__occurred_id", table_name="events")
    op.drop_index("ix_events__occurred", table_name="events")
    op.drop_index("ix_events__event_resource_id_occurred", table_name="events")
    op.drop_index("ix_events__event_related_occurred", table_name="events")
    op.drop_index("ix_events__event_occurred_id", table_name="events")
    op.drop_index("ix_events__event__id", table_name="events")
    op.drop_table("events")
    op.drop_index(op.f("ix_event_resources__updated"), table_name="event_resources")
    op.drop_index(
        "ix_event_resources__resource_id__occurred", table_name="event_resources"
    )
    op.drop_table("event_resources")
