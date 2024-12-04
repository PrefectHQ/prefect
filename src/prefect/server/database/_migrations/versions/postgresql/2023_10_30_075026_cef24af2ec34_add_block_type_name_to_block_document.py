"""Add block_type_name to block document

Revision ID: cef24af2ec34
Revises: bfe653bbf62e
Create Date: 2023-10-30 07:50:26.414043

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "cef24af2ec34"
down_revision = "bfe653bbf62e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.add_column(sa.Column("block_type_name", sa.String(), nullable=True))

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_block_document__block_type_name__name
            ON block_document (block_type_name, name)
            """
        )

    backfill_query = """
        WITH null_block_type_name_cte AS (SELECT id from block_document where block_type_name is null limit 500)
        UPDATE block_document
        SET block_type_name = block_type.name
        FROM block_type, null_block_type_name_cte
        WHERE block_document.block_type_id = block_type.id
        AND block_document.id = null_block_type_name_cte.id;
    """

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        while True:
            # Execute until we've backfilled all block_type_names
            result = conn.execute(sa.text(backfill_query))
            if result.rowcount <= 0:
                break


def downgrade():
    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.drop_column("block_type_name")

    with op.get_context().autocommit_block():
        op.execute(
            """
             DROP INDEX CONCURRENTLY IF EXISTS
             ix_block_document__block_type_name__name
             """
        )
