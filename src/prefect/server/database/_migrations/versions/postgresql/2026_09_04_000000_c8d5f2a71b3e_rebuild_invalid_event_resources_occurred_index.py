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
identically named index in another schema cannot be inspected or rebuilt. Any
invalid `_ccnew` or `_ccold` artifacts left by an interrupted concurrent reindex
are dropped before retrying.
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

        artifacts = (
            op.get_bind()
            .exec_driver_sql(
                """
                SELECT format('%I.%I', n.nspname, c.relname)
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_class target_c
                  ON target_c.relnamespace = c.relnamespace
                 AND target_c.relname = 'ix_event_resources__occurred'
                JOIN pg_index target_i
                  ON target_i.indexrelid = target_c.oid
                 AND target_i.indrelid = i.indrelid
                WHERE i.indrelid = to_regclass('event_resources')
                  AND NOT i.indisvalid
                  AND c.relname ~
                      '^ix_event_resources__occurred_cc(new|old)[0-9]*$'
                  AND c.relam = target_c.relam
                  AND c.reltablespace = target_c.reltablespace
                  AND c.reloptions IS NOT DISTINCT FROM target_c.reloptions
                  AND i.indisunique = target_i.indisunique
                  AND i.indisprimary = target_i.indisprimary
                  AND i.indisexclusion = target_i.indisexclusion
                  AND i.indimmediate = target_i.indimmediate
                  AND i.indnatts = target_i.indnatts
                  AND i.indnkeyatts = target_i.indnkeyatts
                  AND i.indkey = target_i.indkey
                  AND i.indcollation = target_i.indcollation
                  AND i.indclass = target_i.indclass
                  AND i.indoption = target_i.indoption
                  AND pg_get_expr(i.indexprs, i.indrelid) IS NOT DISTINCT FROM
                      pg_get_expr(target_i.indexprs, target_i.indrelid)
                  AND pg_get_expr(i.indpred, i.indrelid) IS NOT DISTINCT FROM
                      pg_get_expr(target_i.indpred, target_i.indrelid)
                """
            )
            .all()
        )
        for artifact in artifacts:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {artifact[0]}")

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
