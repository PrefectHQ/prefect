"""
Fix name on concurrency_limit.tag index.
We prefix unique indexes with 'uq_' instead of 'ix_'.

Revision ID: 7737221bf8a4
Revises: 97e212ea6545
Create Date: 2022-08-07 15:45:50.086584

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7737221bf8a4"
down_revision = "97e212ea6545"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER INDEX ix_concurrency_limit__tag RENAME TO uq_concurrency_limit__tag"
    )


def downgrade():
    op.execute(
        "ALTER INDEX uq_concurrency_limit__tag RENAME TO ix_concurrency_limit__tag"
    )
