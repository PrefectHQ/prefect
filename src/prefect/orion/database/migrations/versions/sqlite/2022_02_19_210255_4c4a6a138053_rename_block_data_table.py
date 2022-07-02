"""Rename block data table

Revision ID: 4c4a6a138053
Revises: 
Create Date: 2022-02-19 21:02:55.886313

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c4a6a138053"
down_revision = "28ae48128c75"
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
