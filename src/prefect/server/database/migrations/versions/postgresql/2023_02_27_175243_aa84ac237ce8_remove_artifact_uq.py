"""Removes unique constraint from artifact table key column

Revision ID: aa84ac237ce8
Revises: 3cad6edf9f13
Create Date: 2023-02-27 17:52:43.438841

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "aa84ac237ce8"
down_revision = "cfdfec5d7557"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f("ix_artifact__key"), table_name="artifact")
    op.create_index(
        op.f("ix_artifact__key"),
        "artifact",
        ["key"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_artifact__key"), table_name="artifact")
    op.create_index(
        op.f("ix_artifact__key"),
        "artifact",
        ["key"],
        unique=True,
    )
