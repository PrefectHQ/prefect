"""Add index on event_resources(event_id) for vacuum performance

Revision ID: a1b2c3d4e5f6
Revises: 79e7a60e43d8
Create Date: 2026-06-10 00:00:00.000000

The db_vacuum `vacuum_events_with_retention_overrides` task deletes
event_resources rows via `event_id IN (SELECT Event.id WHERE ...)`.
Without an index on event_resources.event_id this falls back to a
sequential scan, which times out on large tables and silently breaks
event retention.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "79e7a60e43d8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_event_resources__event_id
        ON event_resources (event_id)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_event_resources__event_id")
