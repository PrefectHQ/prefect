"""Add ix_events__event_related_occurred_md5

Revision ID: 7a73514ca2d6
Revises: 06b7c293bc69
Create Date: 2025-04-04 09:21:58.070532

"""

import sqlalchemy as sa
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
        "ix_events__event_related_occurred_md5",
        "events",
        [sa.literal_column("md5(related::text)"), "event", "occurred"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "ix_events__related_resource_ids_md5",
        "events",
        [sa.literal_column("md5(related_resource_ids::text)"), "event", "occurred"],
        unique=False,
        postgresql_using="btree",
    )


def downgrade():
    op.drop_index(
        "ix_events__event_related_occurred_md5",
        table_name="events",
        postgresql_using="btree",
    )
    op.drop_index(
        "ix_events__related_resource_ids_md5",
        table_name="events",
        postgresql_using="btree",
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
