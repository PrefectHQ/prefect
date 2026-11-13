"""Add index on flow_run(state_type, coalesce(start_time, expected_start_time))

Revision ID: d4a7e1c93f52
Revises: c8d5f2a71b3e
Create Date: 2026-09-15 00:00:00.000000

Filtering flow runs by `state_type` together with a `start_time` bound and
sorting by `START_TIME_ASC`/`START_TIME_DESC` compiles to a predicate and an
`ORDER BY` on `coalesce(flow_run.start_time, flow_run.expected_start_time)`.
The existing expression indexes on that coalesce do not include `state_type`,
so the planner walks the ordered expression index and discards every row in a
different state. On large tables with a small share of matching states this
exceeds the database timeout and the API returns a 500.

Uses CREATE INDEX CONCURRENTLY so the migration does not hold an exclusive
lock on the table. A build that is cancelled or interrupted can leave an
`INVALID` index behind and `IF NOT EXISTS` would then skip it forever, so an
invalid leftover is rebuilt with `REINDEX INDEX CONCURRENTLY` and the result is
verified before the revision is recorded as applied.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d4a7e1c93f52"
down_revision = "c8d5f2a71b3e"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_flow_run__state_type_coalesce_start_time"


def upgrade():
    migration_context = op.get_context()
    with migration_context.autocommit_block():
        if migration_context.as_sql:
            raise RuntimeError("d4a7e1c93f52 requires an online PostgreSQL migration")

        index_query = f"""
            SELECT format('%I.%I', n.nspname, c.relname), i.indisvalid
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE i.indrelid = to_regclass('flow_run')
              AND c.relname = '{INDEX_NAME}'
            """
        index = op.get_bind().exec_driver_sql(index_query).first()
        if index is None:
            op.execute(
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                {INDEX_NAME}
                ON flow_run (state_type, (coalesce(start_time, expected_start_time)))
                """
            )
        elif not index[1]:
            op.execute(f"REINDEX INDEX CONCURRENTLY {index[0]}")

        index = op.get_bind().exec_driver_sql(index_query).first()
        if index is None or not index[1]:
            raise RuntimeError(f"{INDEX_NAME} is missing or invalid after creation")


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
