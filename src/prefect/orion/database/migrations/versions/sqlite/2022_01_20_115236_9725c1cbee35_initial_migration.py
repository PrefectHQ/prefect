"""initial migration

Revision ID: 9725c1cbee35
Revises: 
Create Date: 2022-01-20 11:52:36.295433

"""
from typing import Dict, List, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text

import prefect
from prefect.orion.utilities.schemas import PrefectBaseModel


class DataDocument(PrefectBaseModel):
    """
    DataDocuments were deprecated in September 2022 and this stub is included here
    to simplify removal from the library.
    """

    encoding: str
    blob: bytes


# revision identifiers, used by Alembic.
revision = "9725c1cbee35"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create tables
    op.create_table(
        "flow",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "tags",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flow")),
        sa.UniqueConstraint("name", name=op.f("uq_flow__name")),
    )
    op.create_index(op.f("ix_flow__updated"), "flow", ["updated"], unique=False)
    op.create_table(
        "log",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column(
            "flow_run_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "task_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log")),
    )
    op.create_index(op.f("ix_log__flow_run_id"), "log", ["flow_run_id"], unique=False)
    op.create_index(op.f("ix_log__level"), "log", ["level"], unique=False)
    op.create_index(op.f("ix_log__task_run_id"), "log", ["task_run_id"], unique=False)
    op.create_index(op.f("ix_log__timestamp"), "log", ["timestamp"], unique=False)
    op.create_index(op.f("ix_log__updated"), "log", ["updated"], unique=False)
    op.create_table(
        "concurrency_limit",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False),
        sa.Column(
            "active_slots",
            prefect.orion.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concurrency_limit")),
    )
    op.create_index(
        op.f("ix_concurrency_limit__tag"), "concurrency_limit", ["tag"], unique=True
    )
    op.create_index(
        op.f("ix_concurrency_limit__updated"),
        "concurrency_limit",
        ["updated"],
        unique=False,
    )
    op.create_table(
        "saved_search",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "filters",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_search")),
        sa.UniqueConstraint("name", name=op.f("uq_saved_search__name")),
    )
    op.create_index(
        op.f("ix_saved_search__updated"), "saved_search", ["updated"], unique=False
    )
    op.create_table(
        "task_run_state_cache",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("cache_key", sa.String(), nullable=False),
        sa.Column(
            "cache_expiration",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "task_run_state_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_run_state_cache")),
    )
    op.create_index(
        "ix_task_run_state_cache__cache_key_created_desc",
        "task_run_state_cache",
        ["cache_key", sa.text("created DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_run_state_cache__updated"),
        "task_run_state_cache",
        ["updated"],
        unique=False,
    )
    op.create_table(
        "deployment",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "schedule",
            prefect.orion.utilities.database.Pydantic(
                prefect.orion.schemas.schedules.SCHEDULE_TYPES
            ),
            nullable=True,
        ),
        sa.Column(
            "is_schedule_active", sa.Boolean(), server_default="1", nullable=False
        ),
        sa.Column(
            "tags",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "parameters",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "flow_data",
            prefect.orion.utilities.database.Pydantic(DataDocument),
            nullable=True,
        ),
        sa.Column("flow_runner_type", sa.String(), nullable=True),
        sa.Column(
            "flow_runner_config",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            nullable=True,
        ),
        sa.Column("flow_id", prefect.orion.utilities.database.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["flow_id"],
            ["flow.id"],
            name=op.f("fk_deployment__flow_id__flow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment")),
    )
    op.create_index(
        op.f("ix_deployment__flow_id"), "deployment", ["flow_id"], unique=False
    )
    op.create_index(
        op.f("ix_deployment__updated"), "deployment", ["updated"], unique=False
    )
    op.create_index(
        "uq_deployment__flow_id_name", "deployment", ["flow_id", "name"], unique=True
    )
    op.create_table(
        "flow_run",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "state_type",
            sa.Enum(
                "SCHEDULED",
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="state_type",
            ),
            nullable=True,
        ),
        sa.Column("run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "expected_start_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "next_scheduled_start_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "start_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "end_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column("total_run_time", sa.Interval(), server_default="0", nullable=False),
        sa.Column("flow_version", sa.String(), nullable=True),
        sa.Column(
            "parameters",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column(
            "context",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "empirical_policy",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "tags",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("flow_runner_type", sa.String(), nullable=True),
        sa.Column(
            "flow_runner_config",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            nullable=True,
        ),
        sa.Column(
            "empirical_config",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("auto_scheduled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("flow_id", prefect.orion.utilities.database.UUID(), nullable=False),
        sa.Column(
            "deployment_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "parent_task_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column("state_id", prefect.orion.utilities.database.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deployment_id"],
            ["deployment.id"],
            name=op.f("fk_flow_run__deployment_id__deployment"),
            ondelete="set null",
        ),
        sa.ForeignKeyConstraint(
            ["flow_id"],
            ["flow.id"],
            name=op.f("fk_flow_run__flow_id__flow"),
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_run_id"],
            ["task_run.id"],
            name=op.f("fk_flow_run__parent_task_run_id__task_run"),
            ondelete="SET NULL",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["state_id"],
            ["flow_run_state.id"],
            name=op.f("fk_flow_run__state_id__flow_run_state"),
            ondelete="SET NULL",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flow_run")),
    )
    op.create_index(
        op.f("ix_flow_run__deployment_id"), "flow_run", ["deployment_id"], unique=False
    )
    op.create_index(
        "ix_flow_run__end_time_desc",
        "flow_run",
        [sa.text("end_time DESC")],
        unique=False,
    )
    op.create_index(
        "ix_flow_run__expected_start_time_desc",
        "flow_run",
        [sa.text("expected_start_time DESC")],
        unique=False,
    )
    op.create_index(op.f("ix_flow_run__flow_id"), "flow_run", ["flow_id"], unique=False)
    op.create_index(
        op.f("ix_flow_run__flow_version"), "flow_run", ["flow_version"], unique=False
    )
    op.create_index(op.f("ix_flow_run__name"), "flow_run", ["name"], unique=False)
    op.create_index(
        "ix_flow_run__next_scheduled_start_time_asc",
        "flow_run",
        [sa.text("next_scheduled_start_time ASC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_flow_run__parent_task_run_id"),
        "flow_run",
        ["parent_task_run_id"],
        unique=False,
    )
    op.create_index("ix_flow_run__start_time", "flow_run", ["start_time"], unique=False)
    op.create_index(
        op.f("ix_flow_run__state_id"), "flow_run", ["state_id"], unique=False
    )
    op.create_index("ix_flow_run__state_type", "flow_run", ["state_type"], unique=False)
    op.create_index(op.f("ix_flow_run__updated"), "flow_run", ["updated"], unique=False)
    op.create_index(
        "uq_flow_run__flow_id_idempotency_key",
        "flow_run",
        ["flow_id", "idempotency_key"],
        unique=True,
    )
    op.create_table(
        "flow_run_state",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                "SCHEDULED",
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="state_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column(
            "state_details",
            prefect.orion.utilities.database.Pydantic(
                prefect.orion.schemas.states.StateDetails
            ),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "data",
            prefect.orion.utilities.database.Pydantic(DataDocument),
            nullable=True,
        ),
        sa.Column(
            "flow_run_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.id"],
            name=op.f("fk_flow_run_state__flow_run_id__flow_run"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flow_run_state")),
    )
    op.create_index(
        op.f("ix_flow_run_state__name"), "flow_run_state", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_flow_run_state__type"), "flow_run_state", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_flow_run_state__updated"), "flow_run_state", ["updated"], unique=False
    )
    op.create_index(
        "uq_flow_run_state__flow_run_id_timestamp_desc",
        "flow_run_state",
        ["flow_run_id", sa.text("timestamp DESC")],
        unique=True,
    )
    op.create_table(
        "task_run",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "state_type",
            sa.Enum(
                "SCHEDULED",
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="state_type",
            ),
            nullable=True,
        ),
        sa.Column("run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "expected_start_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "next_scheduled_start_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "start_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "end_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column("total_run_time", sa.Interval(), server_default="0", nullable=False),
        sa.Column("task_key", sa.String(), nullable=False),
        sa.Column("dynamic_key", sa.String(), nullable=False),
        sa.Column("cache_key", sa.String(), nullable=True),
        sa.Column(
            "cache_expiration",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column("task_version", sa.String(), nullable=True),
        sa.Column(
            "empirical_policy",
            prefect.orion.utilities.database.Pydantic(
                prefect.orion.schemas.core.TaskRunPolicy
            ),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "task_inputs",
            prefect.orion.utilities.database.Pydantic(
                Dict[
                    str,
                    List[
                        Union[
                            prefect.orion.schemas.core.TaskRunResult,
                            prefect.orion.schemas.core.Parameter,
                            prefect.orion.schemas.core.Constant,
                        ]
                    ],
                ]
            ),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "tags",
            prefect.orion.utilities.database.JSON(astext_type=Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "flow_run_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.Column("state_id", prefect.orion.utilities.database.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.id"],
            name=op.f("fk_task_run__flow_run_id__flow_run"),
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(
            ["state_id"],
            ["task_run_state.id"],
            name=op.f("fk_task_run__state_id__task_run_state"),
            ondelete="SET NULL",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_run")),
    )
    op.create_index(
        "ix_task_run__end_time_desc",
        "task_run",
        [sa.text("end_time DESC")],
        unique=False,
    )
    op.create_index(
        "ix_task_run__expected_start_time_desc",
        "task_run",
        [sa.text("expected_start_time DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_run__flow_run_id"), "task_run", ["flow_run_id"], unique=False
    )
    op.create_index(op.f("ix_task_run__name"), "task_run", ["name"], unique=False)
    op.create_index(
        "ix_task_run__next_scheduled_start_time_asc",
        "task_run",
        [sa.text("next_scheduled_start_time ASC")],
        unique=False,
    )
    op.create_index("ix_task_run__start_time", "task_run", ["start_time"], unique=False)
    op.create_index(
        op.f("ix_task_run__state_id"), "task_run", ["state_id"], unique=False
    )
    op.create_index("ix_task_run__state_type", "task_run", ["state_type"], unique=False)
    op.create_index(op.f("ix_task_run__updated"), "task_run", ["updated"], unique=False)
    op.create_index(
        "uq_task_run__flow_run_id_task_key_dynamic_key",
        "task_run",
        ["flow_run_id", "task_key", "dynamic_key"],
        unique=True,
    )
    op.create_table(
        "task_run_state",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                "SCHEDULED",
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="state_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column(
            "state_details",
            prefect.orion.utilities.database.Pydantic(
                prefect.orion.schemas.states.StateDetails
            ),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "data",
            prefect.orion.utilities.database.Pydantic(DataDocument),
            nullable=True,
        ),
        sa.Column(
            "task_run_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            ["task_run.id"],
            name=op.f("fk_task_run_state__task_run_id__task_run"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_run_state")),
    )
    op.create_index(
        op.f("ix_task_run_state__name"), "task_run_state", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_task_run_state__type"), "task_run_state", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_task_run_state__updated"), "task_run_state", ["updated"], unique=False
    )
    op.create_index(
        "uq_task_run_state__task_run_id_timestamp_desc",
        "task_run_state",
        ["task_run_id", sa.text("timestamp DESC")],
        unique=True,
    )


def downgrade():
    # Drop tables
    op.drop_index(
        "uq_task_run_state__task_run_id_timestamp_desc", table_name="task_run_state"
    )
    op.drop_index(op.f("ix_task_run_state__updated"), table_name="task_run_state")
    op.drop_index(op.f("ix_task_run_state__type"), table_name="task_run_state")
    op.drop_index(op.f("ix_task_run_state__name"), table_name="task_run_state")
    op.drop_table("task_run_state")
    op.drop_index(
        "uq_task_run__flow_run_id_task_key_dynamic_key", table_name="task_run"
    )
    op.drop_index(op.f("ix_task_run__updated"), table_name="task_run")
    op.drop_index("ix_task_run__state_type", table_name="task_run")
    op.drop_index(op.f("ix_task_run__state_id"), table_name="task_run")
    op.drop_index("ix_task_run__start_time", table_name="task_run")
    op.drop_index("ix_task_run__next_scheduled_start_time_asc", table_name="task_run")
    op.drop_index(op.f("ix_task_run__name"), table_name="task_run")
    op.drop_index(op.f("ix_task_run__flow_run_id"), table_name="task_run")
    op.drop_index("ix_task_run__expected_start_time_desc", table_name="task_run")
    op.drop_index("ix_task_run__end_time_desc", table_name="task_run")
    op.drop_table("task_run")
    op.drop_index(
        "uq_flow_run_state__flow_run_id_timestamp_desc", table_name="flow_run_state"
    )
    op.drop_index(op.f("ix_flow_run_state__updated"), table_name="flow_run_state")
    op.drop_index(op.f("ix_flow_run_state__type"), table_name="flow_run_state")
    op.drop_index(op.f("ix_flow_run_state__name"), table_name="flow_run_state")
    op.drop_table("flow_run_state")
    op.drop_index("uq_flow_run__flow_id_idempotency_key", table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__updated"), table_name="flow_run")
    op.drop_index("ix_flow_run__state_type", table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__state_id"), table_name="flow_run")
    op.drop_index("ix_flow_run__start_time", table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__parent_task_run_id"), table_name="flow_run")
    op.drop_index("ix_flow_run__next_scheduled_start_time_asc", table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__name"), table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__flow_version"), table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__flow_id"), table_name="flow_run")
    op.drop_index("ix_flow_run__expected_start_time_desc", table_name="flow_run")
    op.drop_index("ix_flow_run__end_time_desc", table_name="flow_run")
    op.drop_index(op.f("ix_flow_run__deployment_id"), table_name="flow_run")
    op.drop_table("flow_run")
    op.drop_index("uq_deployment__flow_id_name", table_name="deployment")
    op.drop_index(op.f("ix_deployment__updated"), table_name="deployment")
    op.drop_index(op.f("ix_deployment__flow_id"), table_name="deployment")
    op.drop_table("deployment")
    op.drop_index(
        op.f("ix_task_run_state_cache__updated"), table_name="task_run_state_cache"
    )
    op.drop_index(
        "ix_task_run_state_cache__cache_key_created_desc",
        table_name="task_run_state_cache",
    )
    op.drop_table("task_run_state_cache")
    op.drop_index(op.f("ix_saved_search__updated"), table_name="saved_search")
    op.drop_table("saved_search")
    op.drop_index(op.f("ix_concurrency_limit__updated"), table_name="concurrency_limit")
    op.drop_index(op.f("ix_concurrency_limit__tag"), table_name="concurrency_limit")
    op.drop_table("concurrency_limit")
    op.drop_index(op.f("ix_log__updated"), table_name="log")
    op.drop_index(op.f("ix_log__timestamp"), table_name="log")
    op.drop_index(op.f("ix_log__task_run_id"), table_name="log")
    op.drop_index(op.f("ix_log__level"), table_name="log")
    op.drop_index(op.f("ix_log__flow_run_id"), table_name="log")
    op.drop_table("log")
    op.drop_index(op.f("ix_flow__updated"), table_name="flow")
    op.drop_table("flow")
