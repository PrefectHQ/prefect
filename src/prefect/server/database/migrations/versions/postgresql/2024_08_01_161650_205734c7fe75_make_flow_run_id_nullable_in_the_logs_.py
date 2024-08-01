"""make flow_run_id nullable in the logs table

Revision ID: 205734c7fe75
Revises: 7495a5013e7e
Create Date: 2024-08-01 16:16:50.418202

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "205734c7fe75"
down_revision = "7495a5013e7e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("log") as batch_op:
        batch_op.alter_column("flow_run_id", existing_type=sa.UUID(), nullable=True)


def downgrade():
    with op.batch_alter_table("log") as batch_op:
        batch_op.alter_column("flow_run_id", existing_type=sa.UUID(), nullable=False)
