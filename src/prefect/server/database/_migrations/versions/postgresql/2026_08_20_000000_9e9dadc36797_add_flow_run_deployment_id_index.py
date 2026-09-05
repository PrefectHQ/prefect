"""Add index on flow_run(deployment_id)

Revision ID: 9e9dadc36797
Revises: 50737cdaee36
Create Date: 2026-08-20 00:00:00.000000

Filtering flow runs by deployment (for example the deployment Runs tab, which
calls `POST /api/flow_runs/paginate` with a `deployments.id.any_` filter)
compiles to an equality predicate on `flow_run.deployment_id`. The only
remaining indexes that lead with that column are partial and scheduler-scoped
(`WHERE state_type = 'SCHEDULED'`), so an all-states query sequentially scans
the whole table for both the results query and the pagination COUNT. On large
tables this exceeds the database timeout and the API returns a 500.

Uses CREATE INDEX CONCURRENTLY so the migration does not hold an exclusive
lock on the table (which can be very large on affected deployments). A build
that is cancelled or interrupted can leave an `INVALID` index behind; the plain
`IF NOT EXISTS` would then skip creation and permanently leave the query
without a usable index, so any invalid leftover is dropped and rebuilt first.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9e9dadc36797"
down_revision = "50737cdaee36"
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
                    WHERE c.relname = 'ix_flow_run__deployment_id'
                    AND NOT i.indisvalid
                    """
                )
                .scalar()
            )
            if invalid_index:
                op.execute(
                    "DROP INDEX CONCURRENTLY IF EXISTS ix_flow_run__deployment_id"
                )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_flow_run__deployment_id
            ON flow_run (deployment_id)
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_flow_run__deployment_id")
