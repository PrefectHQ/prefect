"""empty message

Revision ID: adabad235795
Revises: 4a1a0e4f89de
Create Date: 2022-12-05 18:50:28.800545

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "adabad235795"
down_revision = "4a1a0e4f89de"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow", sa.Column("description", sa.TEXT(), nullable=True))


def downgrade():
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_column("description")
