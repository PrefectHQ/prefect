"""Add ix_events__event_related_occurred_md5

Revision ID: 7a73514ca2d6
Revises: 06b7c293bc69
Create Date: 2025-04-04 09:21:58.070532

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7a73514ca2d6"
down_revision = "06b7c293bc69"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX IF EXISTS ix_events__event_related_occurred")
        op.execute("DROP INDEX IF EXISTS ix_events__related_resource_ids")

        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_events__related_gin
            ON events USING gin(related)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_events__event_occurred
            ON events (event, occurred)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_events__related_resource_ids_gin
            ON events USING gin(related_resource_ids)
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_events__related_gin")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_events__event_occurred")
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_events__related_resource_ids_gin"
        )

        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_events__event_related_occurred
            ON events (event, related, occurred)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_events__related_resource_ids
            ON events (related_resource_ids)
            """
        )
