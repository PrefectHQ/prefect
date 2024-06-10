"""add_deployment_version_to_flow_run

Revision ID: bd6efa529f03
Revises: aeea5ee6f070
Create Date: 2024-04-03 09:44:18.666688

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bd6efa529f03"
down_revision = "aeea5ee6f070"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run", sa.Column("deployment_version", sa.String(), nullable=True)
    )
    op.create_index(
        op.f("ix_flow_run__deployment_version"),
        "flow_run",
        ["deployment_version"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_index(op.f("ix_flow_run__deployment_version"), table_name="flow_run")
    op.drop_column("flow_run", "deployment_version")
    # ### end Alembic commands ###
