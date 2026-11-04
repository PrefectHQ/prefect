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

This migration rebuilds an invalid leftover with `REINDEX INDEX CONCURRENTLY`,
which preserves the existing index until its replacement is valid. When the
index is already valid it is a no-op; when it does not exist it is created.
Catalog lookups anchor the index to the resolved `event_resources` table so an
identically named index in another schema cannot be inspected or rebuilt.
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
        if migration_context.as_sql:
            raise RuntimeError("c8d5f2a71b3e requires an online PostgreSQL migration")

        index_query = """
            SELECT format('%I.%I', n.nspname, c.relname), i.indisvalid
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE i.indrelid = to_regclass('event_resources')
              AND c.relname = 'ix_event_resources__occurred'
            """
        index = op.get_bind().exec_driver_sql(index_query).first()
        if index is None:
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_event_resources__occurred
                ON event_resources (occurred)
                """
            )
        elif not index[1]:
            op.execute(f"REINDEX INDEX CONCURRENTLY {index[0]}")

        index = op.get_bind().exec_driver_sql(index_query).first()
        if index is None or not index[1]:
            raise RuntimeError(
                "ix_event_resources__occurred is missing or invalid after creation"
            )


def downgrade():
    # The index is owned by bad1e352c597; this revision only repairs it.
    pass
