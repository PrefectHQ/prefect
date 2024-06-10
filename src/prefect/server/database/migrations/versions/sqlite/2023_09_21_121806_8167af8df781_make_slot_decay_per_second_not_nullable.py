"""Make slot_decay_per_second not nullable

Revision ID: 8167af8df781
Revises: ef674d598dd3
Create Date: 2023-09-21 12:18:06.722322

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8167af8df781"
down_revision = "ef674d598dd3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE concurrency_limit_v2 SET slot_decay_per_second = 0.0 WHERE"
        " slot_decay_per_second is null"
    )
    with op.batch_alter_table("concurrency_limit_v2", schema=None) as batch_op:
        batch_op.alter_column(
            "slot_decay_per_second", existing_type=sa.FLOAT(), nullable=False
        )


def downgrade():
    with op.batch_alter_table("concurrency_limit_v2", schema=None) as batch_op:
        batch_op.alter_column(
            "slot_decay_per_second", existing_type=sa.FLOAT(), nullable=True
        )
