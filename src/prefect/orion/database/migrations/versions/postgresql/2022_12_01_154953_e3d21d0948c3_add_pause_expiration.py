"""Adds pause expiration metadata to flow runs

Revision ID: e3d21d0948c3
Revises: 5e4f924ff96c
Create Date: 2022-12-01 15:49:53.681226

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "e3d21d0948c3"
down_revision = "5e4f924ff96c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run",
        sa.Column(
            "pause_expiration_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_flow_run__pause_expiration_time"),
        "flow_run",
        ["pause_expiration_time"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_flow_run__pause_expiration_time"), table_name="flow_run")
    op.drop_column("flow_run", "pause_expiration_time")
