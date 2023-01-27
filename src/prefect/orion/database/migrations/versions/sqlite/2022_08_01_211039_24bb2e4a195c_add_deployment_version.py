"""Add deployment.version

Revision ID: 24bb2e4a195c
Revises: 905134444e17
Create Date: 2022-08-01 21:10:39.209513

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "24bb2e4a195c"
down_revision = "905134444e17"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("version", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("version")
