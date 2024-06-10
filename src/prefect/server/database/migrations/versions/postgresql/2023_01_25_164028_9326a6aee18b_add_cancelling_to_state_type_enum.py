"""Add CANCELLING to state type enum

Revision ID: 9326a6aee18b
Revises: d481d5058a19
Create Date: 2023-01-25 16:40:28.282753

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9326a6aee18b"
down_revision = "d481d5058a19"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE state_type ADD VALUE IF NOT EXISTS 'CANCELLING';")


def downgrade():
    pass
