"""Add description column to artifact table

Revision ID: 4a1a0e4f89de
Revises: 7d918a392297
Create Date: 2023-03-15 15:30:39.595889

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4a1a0e4f89de"
down_revision = "7d918a392297"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_column("description")
