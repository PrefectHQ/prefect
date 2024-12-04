"""Automations models

Revision ID: 07ed05dfd4ec
Revises: bacc60edce16
Create Date: 2024-04-03 11:16:18.668168

"""

from typing import List

import sqlalchemy as sa
from alembic import op

import prefect
from prefect.server.events.actions import ServerActionTypes
from prefect.server.events.schemas.automations import Firing, ServerTriggerTypes
from prefect.server.events.schemas.events import ReceivedEvent

# revision identifiers, used by Alembic.
revision = "07ed05dfd4ec"
down_revision = "bacc60edce16"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "trigger",
            prefect.server.utilities.database.Pydantic(ServerTriggerTypes),
            nullable=False,
        ),
        sa.Column(
            "actions",
            prefect.server.utilities.database.Pydantic(List[ServerActionTypes]),
            nullable=False,
        ),
        sa.Column(
            "actions_on_trigger",
            prefect.server.utilities.database.Pydantic(List[ServerActionTypes]),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "actions_on_resolve",
            prefect.server.utilities.database.Pydantic(List[ServerActionTypes]),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation")),
    )
    with op.batch_alter_table("automation", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_automation__updated"), ["updated"], unique=False
        )

    op.create_table(
        "automation_bucket",
        sa.Column(
            "automation_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "trigger_id", prefect.server.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "bucketing_key",
            prefect.server.utilities.database.JSON(),
            nullable=False,
        ),
        sa.Column(
            "last_event",
            prefect.server.utilities.database.Pydantic(ReceivedEvent),
            nullable=True,
        ),
        sa.Column(
            "start",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "end",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_operation", sa.String(), nullable=True),
        sa.Column(
            "triggered_at",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name=op.f("fk_automation_bucket__automation_id__automation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_bucket")),
    )
    with op.batch_alter_table("automation_bucket", schema=None) as batch_op:
        batch_op.create_index(
            "ix_automation_bucket__automation_id__end",
            ["automation_id", "end"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_automation_bucket__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            "uq_automation_bucket__automation_id__bucketing_key",
            ["automation_id", "bucketing_key"],
            unique=True,
        )

    op.create_table(
        "automation_related_resource",
        sa.Column(
            "automation_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column(
            "automation_owned_by_resource",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name=op.f("fk_automation_related_resource__automation_id__automation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_related_resource")),
    )
    with op.batch_alter_table("automation_related_resource", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_automation_related_resource__resource_id"),
            ["resource_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_automation_related_resource__updated"),
            ["updated"],
            unique=False,
        )
        batch_op.create_index(
            "uq_automation_related_resource__automation_id__resource_id",
            ["automation_id", "resource_id"],
            unique=True,
        )

    op.create_table(
        "composite_trigger_child_firing",
        sa.Column(
            "automation_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "parent_trigger_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.Column(
            "child_trigger_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "child_firing_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.Column(
            "child_fired_at",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "child_firing",
            prefect.server.utilities.database.Pydantic(Firing),
            nullable=False,
        ),
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name=op.f("fk_composite_trigger_child_firing__automation_id__automation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_composite_trigger_child_firing")),
    )
    with op.batch_alter_table(
        "composite_trigger_child_firing", schema=None
    ) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_composite_trigger_child_firing__updated"),
            ["updated"],
            unique=False,
        )
        batch_op.create_index(
            "uq_composite_trigger_child_firing__a_id__pt_id__ct__id",
            ["automation_id", "parent_trigger_id", "child_trigger_id"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table(
        "composite_trigger_child_firing", schema=None
    ) as batch_op:
        batch_op.drop_index("uq_composite_trigger_child_firing__a_id__pt_id__ct__id")
        batch_op.drop_index(batch_op.f("ix_composite_trigger_child_firing__updated"))

    op.drop_table("composite_trigger_child_firing")
    with op.batch_alter_table("automation_related_resource", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_automation_related_resource__automation_id__resource_id"
        )
        batch_op.drop_index(batch_op.f("ix_automation_related_resource__updated"))
        batch_op.drop_index(batch_op.f("ix_automation_related_resource__resource_id"))

    op.drop_table("automation_related_resource")
    with op.batch_alter_table("automation_bucket", schema=None) as batch_op:
        batch_op.drop_index("uq_automation_bucket__automation_id__bucketing_key")
        batch_op.drop_index(batch_op.f("ix_automation_bucket__updated"))
        batch_op.drop_index("ix_automation_bucket__automation_id__end")

    op.drop_table("automation_bucket")
    with op.batch_alter_table("automation", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_automation__updated"))

    op.drop_table("automation")
