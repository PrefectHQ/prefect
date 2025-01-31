"""add_deployment_concurrency_limit

Revision ID: 97429116795e
Revises: 7495a5013e7e
Create Date: 2024-08-14 15:01:11.152219

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "97429116795e"
down_revision = "7495a5013e7e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment", sa.Column("concurrency_limit", sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column("deployment", "concurrency_limit")
