"""Removes DebugPrintNotification block type

Revision ID: e905fd199258
Revises: 4cdc2ba709a4
Create Date: 2022-07-07 11:28:09.792699

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e905fd199258"
down_revision = "4cdc2ba709a4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM block_type WHERE name = 'Debug Print Notification'
        """
    )


def downgrade():
    # Purely a data migration for 2.0b8. No downgrade necessary.
    pass
