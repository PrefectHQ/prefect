"""add_deployment_version_to_flow_run

Revision ID: 8644a9595a08
Revises: bacc60edce16
Create Date: 2024-04-02 11:45:38.210743

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8644a9595a08"
down_revision = "bacc60edce16"
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


def downgrade():
    op.drop_index(op.f("ix_flow_run__deployment_version"), table_name="flow_run")
    op.drop_column("flow_run", "deployment_version")
