"""Rebuild an invalid event_resources(occurred) index

Revision ID: c8d5f2a71b3e
Revises: 9e9dadc36797
Create Date: 2026-09-04 00:00:00.000000

Revision `bad1e352c597` creates `ix_event_resources__occurred` with
`CREATE INDEX CONCURRENTLY IF NOT EXISTS`. A build that is cancelled or
interrupted (statement timeout, lock timeout, pod restart, two replicas racing
to migrate) leaves an `INVALID` index behind. On the next upgrade
`IF NOT EXISTS` sees the name, skips the build, and the revision is recorded as
applied, so the planner never uses the index and the `db_vacuum` delete on
`event_resources.occurred` falls back to a sequential scan.

This migration drops any invalid leftover and rebuilds it, mirroring the guard
in `50737cdaee36` and `9e9dadc36797`. When the index is already valid, or does
not exist, `IF NOT EXISTS` makes this a no-op or a normal build respectively.
The migration environment serializes PostgreSQL migration runs with a
session-level advisory lock, including across the commits required here.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c8d5f2a71b3e"
down_revision = "9e9dadc36797"
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
                    FROM pg_index i
                    WHERE i.indexrelid =
                        to_regclass('ix_event_resources__occurred')
                    AND NOT i.indisvalid
                    """
                )
                .scalar()
            )
            if invalid_index:
                op.execute(
                    "DROP INDEX CONCURRENTLY IF EXISTS ix_event_resources__occurred"
                )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_event_resources__occurred
            ON event_resources (occurred)
            """
        )


def downgrade():
    # The index is owned by bad1e352c597; this revision only repairs it.
    pass
