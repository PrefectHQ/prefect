"""Add index on event_resources(event_id) for vacuum performance

Revision ID: 14806cb26270
Revises: 79e7a60e43d8
Create Date: 2026-07-20 00:00:00.000000

The db_vacuum retention-override task deletes event_resources rows via an
`event_id IN (SELECT id FROM events WHERE ...)` subquery. Without an index on
`event_id` this falls back to a sequential scan of the whole event_resources
table on every batch, timing out under the API statement timeout on large
deployments and silently deleting nothing.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "14806cb26270"
down_revision = "79e7a60e43d8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_event_resources__event_id
        ON event_resources (event_id)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_event_resources__event_id")
