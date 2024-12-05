"""Add descriptions to deployments.

Revision ID: 3bd87ecdac38
Revises: 42762c37b7bc
Create Date: 2022-06-29 13:34:32.879876

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3bd87ecdac38"
down_revision = "42762c37b7bc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deployment", sa.Column("description", sa.TEXT(), nullable=True))


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("description")
