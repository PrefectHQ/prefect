"""Adds block type slug

Revision ID: f335f9633eec
Revises: 2fe8ef6a6514
Create Date: 2022-07-25 14:25:15.809720

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f335f9633eec"
down_revision = "2fe8ef6a6514"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(), nullable=False))
        batch_op.drop_index("ix_block_type_name_case_insensitive")
        batch_op.drop_index("uq_block_type__name")
        batch_op.create_index("uq_block_type__slug", ["slug"], unique=True)


def downgrade():
    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.drop_index("uq_block_type__slug")
        batch_op.create_index("uq_block_type__name", ["name"], unique=False)
        batch_op.create_index(
            "ix_block_type_name_case_insensitive", ["name"], unique=False
        )
        batch_op.drop_column("slug")
