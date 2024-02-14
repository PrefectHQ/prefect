"""Work queue data migration

Revision ID: 1678f2fb8b33
Revises: b9bda9f142f1
Create Date: 2023-01-31 10:54:42.747849

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "1678f2fb8b33"
down_revision = "b9bda9f142f1"
branch_labels = None
depends_on = None

# 02/14/2024 - removed data migration that added a `default-agent-pool` work pool


def upgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_constraint("uq_work_queue__name")
        batch_op.create_unique_constraint(
            op.f("uq_work_queue__work_pool_id_name"), ["work_pool_id", "name"]
        )
        batch_op.alter_column("work_pool_id", nullable=False)


def downgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_constraint("uq_work_queue__work_pool_id_name")
        batch_op.create_unique_constraint("uq_work_queue__name", ["name"])
