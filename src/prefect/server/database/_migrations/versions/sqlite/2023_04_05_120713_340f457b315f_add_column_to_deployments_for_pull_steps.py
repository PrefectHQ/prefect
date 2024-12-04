"""Add column to deployments for pull steps

Revision ID: 340f457b315f
Revises: 3e1eb8281d5e
Create Date: 2023-04-05 12:07:13.733969

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = "340f457b315f"
down_revision = "3e1eb8281d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pull_steps", sqlite.JSON(), nullable=True))
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("pull_steps")
    op.execute("PRAGMA foreign_keys=ON")
