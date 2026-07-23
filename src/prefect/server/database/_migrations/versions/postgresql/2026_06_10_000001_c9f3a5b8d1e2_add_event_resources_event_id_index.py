"""Add index on event_resources(event_id) for vacuum performance

Revision ID: c9f3a5b8d1e2
Revises: bad1e352c597
Create Date: 2026-06-10 00:00:00.000000

The db_vacuum `vacuum_events_with_retention_overrides` task deletes
event_resources rows via `event_id IN (SELECT Event.id WHERE ...)`.
Without an index on event_resources.event_id this falls back to a
sequential scan, which times out on large tables and silently breaks
event retention.

Uses CREATE INDEX CONCURRENTLY so the migration does not hold an
exclusive lock on the table (which can be very large on affected
deployments).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c9f3a5b8d1e2"
down_revision = "bad1e352c597"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_event_resources__event_id
            ON event_resources (event_id)
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_event_resources__event_id")
