"""Add index on flow_run(state_type, coalesce(start_time, expected_start_time))

Revision ID: a3b9c7d2e5f1
Revises: f416ea180ae1
Create Date: 2026-09-15 00:00:00.000000

Filtering flow runs by `state_type` together with a `start_time` bound and
sorting by `START_TIME_ASC`/`START_TIME_DESC` compiles to a predicate and an
`ORDER BY` on `coalesce(flow_run.start_time, flow_run.expected_start_time)`.
The existing expression indexes on that coalesce do not include `state_type`,
so the planner walks the ordered expression index and discards every row in a
different state.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a3b9c7d2e5f1"
down_revision = "f416ea180ae1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_flow_run__state_type_coalesce_start_time
        ON flow_run (state_type, coalesce(start_time, expected_start_time))
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_flow_run__state_type_coalesce_start_time")
