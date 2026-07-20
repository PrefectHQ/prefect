"""Add index on event_resources(event_id) for vacuum performance

Revision ID: 50737cdaee36
Revises: bad1e352c597
Create Date: 2026-07-20 00:00:00.000000

The db_vacuum retention-override task deletes event_resources rows via an
`event_id IN (SELECT id FROM events WHERE ...)` subquery. Without an index on
`event_id` this falls back to a sequential scan of the whole event_resources
table on every batch, timing out under the API statement timeout on large
deployments and silently deleting nothing.

Uses CREATE INDEX CONCURRENTLY so the migration does not hold an exclusive
lock on the table (which can be very large on affected deployments).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "50737cdaee36"
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
