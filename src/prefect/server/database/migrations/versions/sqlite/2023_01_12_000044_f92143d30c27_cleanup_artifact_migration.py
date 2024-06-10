"""State data migration cleanup

Revision ID: f92143d30c27
Revises: f92143d30c26
Create Date: 2023-01-12 00:00:44.488367

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "f92143d30c27"
down_revision = "f92143d30c26"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    # drop state id columns after data migration
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifact__task_run_state_id"))
        batch_op.drop_column("task_run_state_id")
        batch_op.drop_index(batch_op.f("ix_artifact__flow_run_state_id"))
        batch_op.drop_column("flow_run_state_id")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_flow_run_state__has_data"))
        batch_op.drop_column("has_data")

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_task_run_state__has_data"))
        batch_op.drop_column("has_data")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "flow_run_state_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            ),
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__flow_run_state_id"),
            ["flow_run_state_id"],
            unique=False,
        )
        batch_op.add_column(
            sa.Column(
                "task_run_state_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            ),
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__task_run_state_id"),
            ["task_run_state_id"],
            unique=False,
        )

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("has_data", sa.Boolean))
        batch_op.create_index(
            batch_op.f("ix_flow_run_state__has_data"),
            ["has_data"],
            unique=False,
        )

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("has_data", sa.Boolean))
        batch_op.create_index(
            batch_op.f("ix_task_run_state__has_data"),
            ["has_data"],
            unique=False,
        )
