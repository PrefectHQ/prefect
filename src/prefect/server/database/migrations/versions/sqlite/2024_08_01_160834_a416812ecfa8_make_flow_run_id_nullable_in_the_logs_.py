"""make flow_run_id nullable in the logs table

Revision ID: a416812ecfa8
Revises: 354f1ede7e9f
Create Date: 2024-08-01 16:08:34.762750

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a416812ecfa8"
down_revision = "354f1ede7e9f"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("log", "flow_run_id", existing_type=sa.UUID(), nullable=True)


def downgrade():
    op.alter_column("log", "flow_run_id", existing_type=sa.UUID(), nullable=False)
