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
lock on the table (which can be very large on affected deployments). A build
that is cancelled or interrupted can leave an `INVALID` index behind; the plain
`IF NOT EXISTS` would then skip creation and permanently leave the vacuum query
without a usable index, so any invalid leftover is dropped and rebuilt first.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "50737cdaee36"
down_revision = "bad1e352c597"
branch_labels = None
depends_on = None


def upgrade():
    migration_context = op.get_context()
    with migration_context.autocommit_block():
        if not migration_context.as_sql:
            invalid_index = (
                op.get_bind()
                .exec_driver_sql(
                    """
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_index i ON i.indexrelid = c.oid
                    WHERE c.relname = 'ix_event_resources__event_id'
                    AND NOT i.indisvalid
                    """
                )
                .scalar()
            )
            if invalid_index:
                op.execute(
                    "DROP INDEX CONCURRENTLY IF EXISTS ix_event_resources__event_id"
                )
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
