"""Add work queue name to runs

Revision ID: 77eb737fc759
Revises: 60e428f92a75
Create Date: 2022-08-07 13:44:10.238362

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "77eb737fc759"
down_revision = "60e428f92a75"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("work_queue_name", sa.String(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_deployment__work_queue_name"),
            ["work_queue_name"],
            unique=False,
        )

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("work_queue_name", sa.String(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_flow_run__work_queue_name"),
            ["work_queue_name"],
            unique=False,
        )

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column("filter", nullable=True, server_default=None)


def downgrade():

    op.execute(
        """
        UPDATE work_queue
        SET filter = '{}'
        WHERE filter IS NULL;
        """
    )

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column("filter", nullable=False, server_default=sa.text("'{}'"))

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_flow_run__work_queue_name"))
        batch_op.drop_column("work_queue_name")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployment__work_queue_name"))
        batch_op.drop_column("work_queue_name")
