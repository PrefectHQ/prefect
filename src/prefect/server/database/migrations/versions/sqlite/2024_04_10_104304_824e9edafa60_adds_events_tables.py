"""Add `events` and `event_resources` tables

Revision ID: 824e9edafa60
Revises: 2b6c2b548f95
Create Date: 2024-04-10 10:43:04.801473

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "824e9edafa60"
down_revision = "2b6c2b548f95"
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_resources")),
    )
    with op.batch_alter_table("event_resources", schema=None) as batch_op:
        batch_op.create_index(
            "ix_event_resources__resource_id__occurred",
            ["resource_id", "occurred"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_event_resources__updated"), ["updated"], unique=False
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
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "related_resource_ids",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "related",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "payload",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index("ix_events__event__id", ["event", "id"], unique=False)
        batch_op.create_index(
            "ix_events__event_occurred_id", ["event", "occurred", "id"], unique=False
        )
        batch_op.create_index(
            "ix_events__event_related_occurred",
            ["event", "related", "occurred"],
            unique=False,
        )
        batch_op.create_index(
            "ix_events__event_resource_id_occurred",
            ["event", "resource_id", "occurred"],
            unique=False,
        )
        batch_op.create_index("ix_events__occurred", ["occurred"], unique=False)
        batch_op.create_index(
            "ix_events__occurred_id", ["occurred", "id"], unique=False
        )
        batch_op.create_index(
            "ix_events__related_resource_ids", ["related_resource_ids"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_events__updated"), ["updated"], unique=False
        )


def downgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_events__updated"))
        batch_op.drop_index("ix_events__related_resource_ids")
        batch_op.drop_index("ix_events__occurred_id")
        batch_op.drop_index("ix_events__occurred")
        batch_op.drop_index("ix_events__event_resource_id_occurred")
        batch_op.drop_index("ix_events__event_related_occurred")
        batch_op.drop_index("ix_events__event_occurred_id")
        batch_op.drop_index("ix_events__event__id")

    op.drop_table("events")
    with op.batch_alter_table("event_resources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_event_resources__updated"))
        batch_op.drop_index("ix_event_resources__resource_id__occurred")

    op.drop_table("event_resources")
