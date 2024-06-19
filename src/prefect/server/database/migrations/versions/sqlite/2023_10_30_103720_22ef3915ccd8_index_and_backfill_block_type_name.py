"""Index and backfill block_type_name

Revision ID: 22ef3915ccd8
Revises: cef24af2ec34
Create Date: 2023-10-30 10:37:20.922002

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "22ef3915ccd8"
down_revision = "cef24af2ec34"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_block_document__block_type_name_name"),
            ["block_type_name", "name"],
            unique=False,
        )

    backfill_query = """
        UPDATE block_document
        SET block_type_name = (SELECT name from block_type where block_type.id = block_document.block_type_id)
        WHERE block_document.id in (SELECT id from block_document where block_type_name is null limit 500);
    """

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        while True:
            # Execute until we've backfilled all block_type_names
            result = conn.execute(sa.text(backfill_query))
            if result.rowcount <= 0:
                break


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
             DROP INDEX
             ix_block_document__block_type_name_name
             """
        )
