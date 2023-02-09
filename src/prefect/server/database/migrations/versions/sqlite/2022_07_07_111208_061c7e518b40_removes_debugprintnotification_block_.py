"""Removes DebugPrintNotification block type

Revision ID: 061c7e518b40
Revises: e2dae764a603
Create Date: 2022-07-07 11:12:08.749298

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "061c7e518b40"
down_revision = "e2dae764a603"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM block_type WHERE name = "Debug Print Notification"
        """
    )


def downgrade():
    # Purely a data migration for 2.0b8. No downgrade necessary.
    pass
