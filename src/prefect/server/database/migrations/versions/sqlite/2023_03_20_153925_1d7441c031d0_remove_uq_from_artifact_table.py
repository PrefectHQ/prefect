"""Removes unique constraint from artifact table key column

Revision ID: 1d7441c031d0
Revises: cf1159bd0d3c
Create Date: 2023-03-20 15:39:25.077241

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "1d7441c031d0"
down_revision = "cf1159bd0d3c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")
    op.drop_index(op.f("ix_artifact__key"), table_name="artifact")
    op.create_index(
        op.f("ix_artifact__key"),
        "artifact",
        ["key"],
        unique=False,
    )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")
    op.drop_index(op.f("ix_artifact__key"), table_name="artifact")
    op.create_index(
        op.f("ix_artifact__key"),
        "artifact",
        ["key"],
        unique=True,
    )
    op.execute("PRAGMA foreign_keys=ON")
