"""State data migration cleanup

Revision ID: 2882cd2df465
Revises: 2882cd2df464
Create Date: 2023-01-13 04:55:02.358638

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "2882cd2df465"
down_revision = "2882cd2df464"
branch_labels = None
depends_on = None


def upgrade():
    # drop state id columns after data migration
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifact__task_run_state_id"))
        batch_op.drop_column("task_run_state_id")
        batch_op.drop_index(batch_op.f("ix_artifact__flow_run_state_id"))
        batch_op.drop_column("flow_run_state_id")
        # batch_op.drop_index(batch_op.f("ix_artifact__data"))


def downgrade():
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "flow_run_state_id",
                prefect.orion.utilities.database.UUID(),
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
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            ),
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__task_run_state_id"),
            ["task_run_state_id"],
            unique=False,
        )
        # batch_op.create_index(
        #     batch_op.f("ix_artifact__data"),
        #     ["data"],
        #     unique=False,
        # )
