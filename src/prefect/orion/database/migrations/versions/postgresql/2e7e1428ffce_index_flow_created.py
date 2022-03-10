"""Index Flow.created

Revision ID: 2e7e1428ffce
Revises: b68b3cad6b8a
Create Date: 2022-03-10 10:27:13.015390

"""
from alembic import op
import sqlalchemy as sa
import prefect


# revision identifiers, used by Alembic.
revision = "2e7e1428ffce"
down_revision = "b68b3cad6b8a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.create_index("created", ["created"], unique=False)


def downgrade():
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_index("created")
