"""Rename block data table

Revision ID: d9d98a9ebb6f
Revises: 
Create Date: 2022-02-19 20:55:43.397189

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "d9d98a9ebb6f"
down_revision = "679e695af6ba"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE block_data
        RENAME TO block;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE block
        RENAME TO block_data;
        """
    )
