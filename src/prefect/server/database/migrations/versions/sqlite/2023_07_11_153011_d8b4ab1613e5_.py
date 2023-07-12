"""empty message

Revision ID: d8b4ab1613e5
Revises: f9b1d2ba9281
Create Date: 2023-07-11 15:30:11.557966

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d8b4ab1613e5"
down_revision = "f9b1d2ba9281"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("concurrency_limit", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slots", sa.Integer(), nullable=False))


def downgrade():
    with op.batch_alter_table("concurrency_limit", schema=None) as batch_op:
        batch_op.drop_column("slots")
