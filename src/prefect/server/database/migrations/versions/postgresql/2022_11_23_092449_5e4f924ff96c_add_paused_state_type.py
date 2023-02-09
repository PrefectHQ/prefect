"""Add PAUSED to state type enum

Revision ID: 5e4f924ff96c
Revises: 5d526270ddb4
Create Date: 2022-11-23 09:24:49.826750

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "5e4f924ff96c"
down_revision = "5d526270ddb4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE state_type ADD VALUE IF NOT EXISTS 'PAUSED';")


def downgrade():
    # cannot remove values from an enum without changing data
    pass
