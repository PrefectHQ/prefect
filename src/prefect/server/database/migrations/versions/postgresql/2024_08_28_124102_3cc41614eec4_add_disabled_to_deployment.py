"""add_disabled_to_deployment

Revision ID: 3cc41614eec4
Revises: 97429116795e
Create Date: 2024-08-28 12:41:02.758100

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3cc41614eec4"
down_revision = "97429116795e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column("disabled", sa.Boolean(), server_default="0", nullable=False),
    )


def downgrade():
    op.drop_column("deployment", "disabled")
