"""Add block_type_name to block document

Revision ID: cef24af2ec34
Revises: f3165ae0a213
Create Date: 2023-10-30 07:50:26.414043

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "cef24af2ec34"
down_revision = "f3165ae0a213"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.add_column(sa.Column("block_type_name", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.drop_column("block_type_name")
