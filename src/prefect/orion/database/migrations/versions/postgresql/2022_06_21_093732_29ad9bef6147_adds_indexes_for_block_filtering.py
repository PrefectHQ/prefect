"""Adds indexes for block filtering

Revision ID: 29ad9bef6147
Revises: d335ad57d5ba
Create Date: 2022-06-21 09:37:32.382898

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "29ad9bef6147"
down_revision = "d335ad57d5ba"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY 
            trgm_ix_block_type_name 
            ON block_type USING gin (name gin_trgm_ops);
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY trgm_ix_block_type_name;
            """
        )
