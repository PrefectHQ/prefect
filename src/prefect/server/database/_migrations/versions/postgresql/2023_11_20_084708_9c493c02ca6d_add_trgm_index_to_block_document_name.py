"""Add trgm index to block_document.name

Revision ID: 9c493c02ca6d
Revises: cef24af2ec34
Create Date: 2023-11-20 08:47:08.929487

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9c493c02ca6d"
down_revision = "cef24af2ec34"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            trgm_ix_block_document_name
            ON block_document USING gin (name gin_trgm_ops);
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS
            trgm_ix_block_document_name;
            """
        )
