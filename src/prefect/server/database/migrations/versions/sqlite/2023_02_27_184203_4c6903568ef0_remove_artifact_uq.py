"""Removes unique constraint from key column in artifact table

Revision ID: 4c6903568ef0
Revises: 8d148e44e669
Create Date: 2023-02-27 18:42:03.560057

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c6903568ef0"
down_revision = "8d148e44e669"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index("ix_artifact__key")
        batch_op.create_index(batch_op.f("ix_artifact__key"), ["key"], unique=False)


def downgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifact__key"))
        batch_op.create_index("ix_artifact__key", ["key"], unique=True)
