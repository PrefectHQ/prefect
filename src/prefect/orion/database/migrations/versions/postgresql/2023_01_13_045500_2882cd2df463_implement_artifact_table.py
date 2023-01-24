"""Implements the artifact table and migrates run results

Revision ID: 2882cd2df463
Revises: d481d5058a19
Create Date: 2023-01-13 04:55:00.358638

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "2882cd2df463"
down_revision = "d481d5058a19"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artifact",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("metadata_", sa.JSON(), nullable=True),
        sa.Column(
            "task_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "task_run_state_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_state_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.id"],
            name=op.f("fk_artifact__flow_run_id__flow_run"),
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_state_id"],
            ["flow_run_state.id"],
            name=op.f("fk_artifact__flow_run_state_id__flow_run_state"),
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            ["task_run.id"],
            name=op.f("fk_artifact__task_run_id__task_run"),
        ),
        sa.ForeignKeyConstraint(
            ["task_run_state_id"],
            ["task_run_state.id"],
            name=op.f("fk_artifact__task_run_state_id__task_run_state"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact")),
    )
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_artifact__flow_run_id"),
            ["flow_run_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__flow_run_state_id"),
            ["flow_run_state_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_artifact__key"), ["key"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_artifact__task_run_id"),
            ["task_run_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__task_run_state_id"),
            ["task_run_state_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__updated"), ["updated"], unique=False
        )

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")
        batch_op.add_column(
            sa.Column(
                "result_artifact_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_flow_run_state__result_artifact_id"),
            ["result_artifact_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run_state__result_artifact_id__artifact"),
            "artifact",
            ["result_artifact_id"],
            ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")
        batch_op.add_column(
            sa.Column(
                "result_artifact_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_task_run_state__result_artifact_id"),
            ["result_artifact_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_task_run_state__result_artifact_id__artifact"),
            "artifact",
            ["result_artifact_id"],
            ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")
        batch_op.add_column(sa.Column("has_data", sa.Boolean))

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")
        batch_op.add_column(sa.Column("has_data", sa.Boolean))

    op.execute(
        "UPDATE task_run_state SET has_data = (_data IS NOT NULL or _data != 'null')"
    )
    op.create_index(
        op.f("ix_task_run_state__has_data"),
        "task_run_state",
        ["has_data"],
        unique=False,
    )
    op.execute(
        "UPDATE flow_run_state SET has_data = (_data IS NOT NULL or _data != 'null')"
    )
    op.create_index(
        op.f("ix_flow_run_state__has_data"),
        "flow_run_state",
        ["has_data"],
        unique=False,
    )


def downgrade():

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_task_run_state__has_data"))
        batch_op.drop_column("has_data")
        batch_op.alter_column("_data", new_column_name="data")
        batch_op.drop_constraint(
            batch_op.f("fk_task_run_state__result_artifact_id__artifact"),
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_task_run_state__result_artifact_id"))
        batch_op.drop_column("result_artifact_id")
        batch_op.alter_column("_data", new_column_name="data")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_flow_run_state__has_data"))
        batch_op.drop_column("has_data")
        batch_op.alter_column("_data", new_column_name="data")
        batch_op.drop_constraint(
            batch_op.f("fk_flow_run_state__result_artifact_id__artifact"),
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_flow_run_state__result_artifact_id"))
        batch_op.drop_column("result_artifact_id")
        batch_op.alter_column("_data", new_column_name="data")

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifact__updated"))
        batch_op.drop_index(batch_op.f("ix_artifact__task_run_id"))
        batch_op.drop_index(batch_op.f("ix_artifact__key"))
        batch_op.drop_index(batch_op.f("ix_artifact__flow_run_id"))

    op.drop_table("artifact")
