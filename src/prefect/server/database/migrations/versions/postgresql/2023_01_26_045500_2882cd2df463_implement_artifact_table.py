"""Implements the artifact table and migrates run results

Revision ID: 2882cd2df463
Revises: d481d5058a19
Create Date: 2023-01-26 04:55:00.358638

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "2882cd2df463"
down_revision = "9326a6aee18b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artifact",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("metadata_", sa.JSON(), nullable=True),
        sa.Column(
            "task_run_id", prefect.server.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "task_run_state_id", prefect.server.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_id", prefect.server.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_state_id", prefect.server.utilities.database.UUID(), nullable=True
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
    op.create_index(
        op.f("ix_artifact__flow_run_id"), "artifact", ["flow_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact__flow_run_state_id"),
        "artifact",
        ["flow_run_state_id"],
        unique=False,
    )
    op.create_index(op.f("ix_artifact__key"), "artifact", ["key"], unique=True)
    op.create_index(
        op.f("ix_artifact__task_run_id"), "artifact", ["task_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact__task_run_state_id"),
        "artifact",
        ["task_run_state_id"],
        unique=False,
    )
    op.create_index(op.f("ix_artifact__updated"), "artifact", ["updated"], unique=False)

    op.add_column(
        "flow_run_state",
        sa.Column(
            "result_artifact_id",
            prefect.server.utilities.database.UUID(),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_flow_run_state__result_artifact_id"),
        "flow_run_state",
        ["result_artifact_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_flow_run_state__result_artifact_id__artifact"),
        "flow_run_state",
        "artifact",
        ["result_artifact_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )
    op.add_column(
        "task_run_state",
        sa.Column(
            "result_artifact_id",
            prefect.server.utilities.database.UUID(),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_task_run_state__result_artifact_id"),
        "task_run_state",
        ["result_artifact_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_task_run_state__result_artifact_id__artifact"),
        "task_run_state",
        "artifact",
        ["result_artifact_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade():
    op.drop_constraint(
        op.f("fk_task_run_state__result_artifact_id__artifact"),
        "task_run_state",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_task_run_state__result_artifact_id"), table_name="task_run_state"
    )
    op.drop_column("task_run_state", "result_artifact_id")
    op.drop_constraint(
        op.f("fk_flow_run_state__result_artifact_id__artifact"),
        "flow_run_state",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_flow_run_state__result_artifact_id"), table_name="flow_run_state"
    )
    op.drop_column("flow_run_state", "result_artifact_id")

    op.drop_index(op.f("ix_artifact__updated"), table_name="artifact")
    op.drop_index(op.f("ix_artifact__task_run_id"), table_name="artifact")
    op.drop_index(op.f("ix_artifact__key"), table_name="artifact")
    op.drop_index(op.f("ix_artifact__flow_run_id"), table_name="artifact")
    op.drop_table("artifact")
