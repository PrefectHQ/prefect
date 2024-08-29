"""add_disabled_to_deployment

Revision ID: a941fb41767c
Revises: 20fbd53b3cef
Create Date: 2024-08-28 12:04:22.108067

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a941fb41767c"
down_revision = "20fbd53b3cef"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("disabled", sa.Boolean(), server_default="0", nullable=False)
        )


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("disabled")
