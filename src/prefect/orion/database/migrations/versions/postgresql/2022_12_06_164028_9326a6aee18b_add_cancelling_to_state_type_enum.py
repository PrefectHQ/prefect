"""Add CANCELLING to state type enum

Revision ID: 9326a6aee18b
Revises: 5e4f924ff96c
Create Date: 2022-12-06 16:40:28.282753

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "9326a6aee18b"
down_revision = "5e4f924ff96c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE state_type ADD VALUE IF NOT EXISTS 'CANCELLING';")


def downgrade():
    pass
