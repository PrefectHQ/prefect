"""Add descriptions to task and flow runs

Revision ID: 813ddf14e2de
Revises: 7296741dff68
Create Date: 2022-06-29 13:54:32.981105

"""
from alembic import op
import sqlalchemy as sa
import prefect


# revision identifiers, used by Alembic.
revision = "813ddf14e2de"
down_revision = "7296741dff68"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow_run", sa.Column("description", sa.TEXT(), nullable=True))
    op.add_column("task_run", sa.Column("description", sa.TEXT(), nullable=True))


def downgrade():
    op.drop_column("flow_run", "description")
    op.drop_column("task_run", "description")
