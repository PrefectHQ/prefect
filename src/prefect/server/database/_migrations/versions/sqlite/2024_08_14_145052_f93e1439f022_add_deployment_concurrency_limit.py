"""add_deployment_concurrency_limit

Revision ID: f93e1439f022
Revises: 354f1ede7e9f
Create Date: 2024-08-14 14:50:52.420436

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f93e1439f022"
down_revision = "354f1ede7e9f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("concurrency_limit", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("concurrency_limit")
