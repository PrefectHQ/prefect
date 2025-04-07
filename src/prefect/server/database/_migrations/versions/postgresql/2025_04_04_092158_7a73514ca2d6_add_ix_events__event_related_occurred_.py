"""Add ix_events__event_related_occurred_md5

Revision ID: 7a73514ca2d6
Revises: 06b7c293bc69
Create Date: 2025-04-04 09:21:58.070532

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7a73514ca2d6"
down_revision = "06b7c293bc69"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_events__event_related_occurred", table_name="events")
    op.drop_index("ix_events__related_resource_ids", table_name="events")
    op.create_index(
        "ix_events__related_gin",
        "events",
        ["related"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_events__event_occurred",
        "events",
        ["event", "occurred"],
        unique=False,
    )
    op.create_index(
        "ix_events__related_resource_ids_gin",
        "events",
        ["related_resource_ids"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade():
    op.drop_index(
        "ix_events__related_gin",
        table_name="events",
    )
    op.drop_index(
        "ix_events__event_occurred",
        table_name="events",
    )
    op.drop_index(
        "ix_events__related_resource_ids_gin",
        table_name="events",
    )
    op.create_index(
        "ix_events__event_related_occurred",
        "events",
        ["event", "related", "occurred"],
        unique=False,
    )
    op.create_index(
        "ix_events__related_resource_ids",
        "events",
        ["related_resource_ids"],
        unique=False,
    )
