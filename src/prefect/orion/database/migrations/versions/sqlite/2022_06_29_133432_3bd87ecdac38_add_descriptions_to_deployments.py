"""Add descriptions to deployments.

Revision ID: 3bd87ecdac38
Revises: dff8da7a6c2c
Create Date: 2022-06-29 13:34:32.879876

"""
from alembic import op
import sqlalchemy as sa
import prefect


# revision identifiers, used by Alembic.
revision = "3bd87ecdac38"
down_revision = "dff8da7a6c2c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deployment", sa.Column("description", sa.TEXT(), nullable=True))


def downgrade():
    op.drop_column("deployment", "description")
