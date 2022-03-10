"""Index Flow.created

Revision ID: 71a57ec351d1
Revises: c8ff35f94028
Create Date: 2022-03-10 10:25:00.099168

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "71a57ec351d1"
down_revision = "c8ff35f94028"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.create_index("ix_flow__created", ["created"], unique=False)


def downgrade():
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_index("ix_flow__created")
