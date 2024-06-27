"""Add deployment.version

Revision ID: 97e212ea6545
Revises: fa985d474982
Create Date: 2022-08-01 21:12:51.296800

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "97e212ea6545"
down_revision = "fa985d474982"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("version", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("version")
