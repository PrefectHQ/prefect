"""
Fix name on concurrency_limit.tag index.
We prefix unique indexes with 'uq_' instead of 'ix_'.

Revision ID: 53c19b31aa09
Revises: 24bb2e4a195c
Create Date: 2022-08-07 15:43:19.528922

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "53c19b31aa09"
down_revision = "24bb2e4a195c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("concurrency_limit", schema=None) as batch_op:
        batch_op.drop_index("ix_concurrency_limit__tag")
        batch_op.create_index("uq_concurrency_limit__tag", ["tag"], unique=True)


def downgrade():
    with op.batch_alter_table("concurrency_limit", schema=None) as batch_op:
        batch_op.drop_index("uq_concurrency_limit__tag")
        batch_op.create_index("ix_concurrency_limit__tag", ["tag"], unique=False)
