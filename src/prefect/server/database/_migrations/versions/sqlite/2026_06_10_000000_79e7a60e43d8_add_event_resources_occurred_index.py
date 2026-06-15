"""Add index on event_resources(occurred) for vacuum performance

Revision ID: 79e7a60e43d8
Revises: 2095de406cbe
Create Date: 2026-06-10 00:00:00.000000

The db_vacuum service deletes old event_resources rows filtered by
`occurred < retention_cutoff`.  Without a dedicated index the query
falls back to a sequential scan on large tables, timing out every
cycle and silently breaking event retention.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "79e7a60e43d8"
down_revision = "2095de406cbe"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_event_resources__occurred
        ON event_resources (occurred)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_event_resources__occurred")
