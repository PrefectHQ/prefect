"""empty message

Revision ID: 41e5ed9e1034
Revises: 8ea825da948d
Create Date: 2022-10-31 16:17:19.166384

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "41e5ed9e1034"
down_revision = "8ea825da948d"
branch_labels = None
depends_on = None


def upgrade():
    # install pg_trgm
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY
            trgm_ix_work_queue_name
            ON work_queue USING gin (name gin_trgm_ops);
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY trgm_ix_work_queue_name;
            """
        )
