"""Work queue data migration

Revision ID: f98ae6d8e2cc
Revises: 0a1250a5aa25
Create Date: 2023-01-31 11:05:43.356002

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f98ae6d8e2cc"
down_revision = "0a1250a5aa25"
branch_labels = None
depends_on = None

# 02/14/2024 - removed data migration that added a `default-agent-pool` work pool


def upgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_constraint("uq_work_queue__name", type_="unique")
        batch_op.create_unique_constraint(
            "uq_work_queue__work_pool_id_name", ["work_pool_id", "name"]
        )
        batch_op.alter_column(
            "work_pool_id", existing_type=sa.INTEGER(), nullable=False
        )


def downgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column("work_pool_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.drop_constraint("uq_work_queue__work_pool_id_name", type_="unique")
        batch_op.create_unique_constraint("uq_work_queue__name", ["name"])
