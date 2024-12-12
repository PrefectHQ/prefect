"""Removing default storage block document.

Revision ID: 0f27d462bf6d
Revises: 112c68143fc3
Create Date: 2022-07-14 11:40:39.277740

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0f27d462bf6d"
down_revision = "112c68143fc3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(
        "ix_block_document__is_default_storage_block_document",
        table_name="block_document",
    )
    op.drop_column("block_document", "is_default_storage_block_document")


def downgrade():
    op.add_column(
        "block_document",
        sa.Column(
            "is_default_storage_block_document",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.create_index(
        "ix_block_document__is_default_storage_block_document",
        "block_document",
        ["is_default_storage_block_document"],
        unique=False,
    )
