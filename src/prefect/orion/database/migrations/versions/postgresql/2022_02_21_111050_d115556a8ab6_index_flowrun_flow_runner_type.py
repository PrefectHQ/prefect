"""Index FlowRun.flow_runner_type

Revision ID: d115556a8ab6
Revises: 4799f657a6a1
Create Date: 2022-02-21 11:10:50.989062

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "d115556a8ab6"
down_revision = "4799f657a6a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_flow_run__flow_runner_type"),
        "flow_run",
        ["flow_runner_type"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_flow_run__flow_runner_type"), table_name="flow_run")
