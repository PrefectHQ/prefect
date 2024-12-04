"""Make slot_decay_per_second not nullable

Revision ID: 4e9a6f93eb6c
Revises: db0eb3973a54
Create Date: 2023-09-21 13:01:25.580703

"""

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4e9a6f93eb6c"
down_revision = "db0eb3973a54"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE concurrency_limit_v2 SET slot_decay_per_second = 0.0 WHERE"
        " slot_decay_per_second is null"
    )
    op.alter_column(
        "concurrency_limit_v2",
        "slot_decay_per_second",
        existing_type=postgresql.DOUBLE_PRECISION(precision=53),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "concurrency_limit_v2",
        "slot_decay_per_second",
        existing_type=postgresql.DOUBLE_PRECISION(precision=53),
        nullable=True,
    )
