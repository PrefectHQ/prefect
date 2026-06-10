"""Add index on event_resources(occurred) for vacuum performance

Revision ID: bad1e352c597
Revises: 7218aad17905
Create Date: 2026-06-10 00:00:00.000000

The db_vacuum service deletes old event_resources rows filtered by
`occurred < retention_cutoff`.  Without a dedicated index the query
falls back to a sequential scan on large tables, timing out every
cycle and silently breaking event retention.

Uses CREATE INDEX CONCURRENTLY so the migration does not hold an
exclusive lock on the table (which can be very large on affected
deployments).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "bad1e352c597"
down_revision = "7218aad17905"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_event_resources__occurred
            ON event_resources (occurred)
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_event_resources__occurred")
