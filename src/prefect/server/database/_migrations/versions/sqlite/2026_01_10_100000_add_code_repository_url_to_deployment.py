"""Add code_repository_url to deployment

Revision ID: a1b2c3d4e5f6
Revises: 9e83011d1f2a
Create Date: 2026-01-10 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9e83011d1f2a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("code_repository_url", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("code_repository_url")
