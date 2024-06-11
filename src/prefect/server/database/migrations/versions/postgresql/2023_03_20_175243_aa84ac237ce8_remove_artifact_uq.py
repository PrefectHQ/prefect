"""Removes unique constraint from artifact table key column
Revision ID: aa84ac237ce8
Revises: 4a1a0e4f89de
Create Date: 2023-03-20 17:52:43.438841
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "aa84ac237ce8"
down_revision = "4a1a0e4f89de"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index("ix_artifact__key")
        batch_op.create_index(
            "ix_artifact__key",
            ["key"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index("ix_artifact__key")
        batch_op.create_index(
            "ix_artifact__key",
            ["key"],
            unique=True,
        )
