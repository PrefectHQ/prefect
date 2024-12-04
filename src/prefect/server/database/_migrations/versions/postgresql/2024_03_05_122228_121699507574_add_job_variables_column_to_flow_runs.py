"""Add job_variables column to flow-runs

Revision ID: 121699507574
Revises: 8cf4d4933848
Create Date: 2024-03-05 12:22:28.460541

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "121699507574"
down_revision = "8cf4d4933848"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run",
        sa.Column(
            "job_variables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("flow_run", "job_variables")
