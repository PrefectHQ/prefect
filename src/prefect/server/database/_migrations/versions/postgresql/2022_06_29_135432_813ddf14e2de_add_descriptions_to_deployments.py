"""Add descriptions to deployments.

Revision ID: 813ddf14e2de
Revises: 2f46fc3f3beb
Create Date: 2022-06-29 13:54:32.981105

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "813ddf14e2de"
down_revision = "2f46fc3f3beb"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deployment", sa.Column("description", sa.TEXT(), nullable=True))


def downgrade():
    op.drop_column("deployment", "description")
