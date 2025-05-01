"""Remove flow run notifications

Revision ID: 4160a4841eed
Revises: ca25ef67243a
Create Date: 2025-04-29 11:29:02.482732

"""

import json
import textwrap
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

import prefect
from prefect.logging.loggers import get_logger

# revision identifiers, used by Alembic.
revision = "4160a4841eed"
down_revision = "7a73514ca2d6"
branch_labels = None
depends_on = None


DEFAULT_BODY = textwrap.dedent("""
Flow run {{ flow.name }}/{{ flow_run.name }} observed in state `{{ flow_run.state.name }}` at {{ flow_run.state.timestamp }}.
Flow ID: {{ flow_run.flow_id }}
Flow run ID: {{ flow_run.id }}
Flow run URL: {{ flow_run|ui_url }}
State message: {{ flow_run.state.message }}
""")

PLACEHOLDER_MAP = {
    "flow_run_notification_policy_id": "Event ID {{ event.id }}",
    "flow_id": "{{ flow.id }}",
    "flow_name": "{{ flow.name }}",
    "flow_run_url": "{{ flow_run|ui_url }}",
    "flow_run_id": "{{ flow_run.id }}",
    "flow_run_name": "{{ flow_run.name }}",
    "flow_run_parameters": "{{ flow_run.parameters }}",
    "flow_run_state_type": "{{ flow_run.state.type }}",
    "flow_run_state_name": "{{ flow_run.state.name }}",
    "flow_run_state_timestamp": "{{ flow_run.state.timestamp }}",
    "flow_run_state_message": "{{ flow_run.state.message }}",
}


def upgrade():
    conn = op.get_bind()
    with op.get_context().autocommit_block():
        rows = (
            conn.execute(
                sa.text(
                    "SELECT id, is_active, state_names, tags, message_template, block_document_id FROM flow_run_notification_policy"
                ),
            )
        ).fetchall()
        if len(rows) > 0:
            for row in rows:
                row: sa.Row[tuple[UUID, bool, list[str], list[str], str | None, UUID]]

                is_active = row[1]
                state_names = row[2]
                tags = row[3]
                message_template = row[4]
                block_document_id = row[5]

                trigger = {
                    "id": str(uuid4()),
                    "type": "event",
                    "after": [],
                    "match": {"prefect.resource.id": "prefect.flow-run.*"},
                    "expect": list(
                        {f"prefect.flow-run.{state_name}" for state_name in state_names}
                    )
                    if state_names
                    else ["prefect.flow-run.*"],
                    "within": 10,
                    "posture": "Reactive",
                    "for_each": ["prefect.resource.id"],
                    "threshold": 1,
                    "match_related": {
                        "prefect.resource.id": [f"prefect.tag.{tag}" for tag in tags],
                        "prefect.resource.role": "tag",
                    }
                    if tags
                    else {},
                }

                actions = [
                    {
                        "body": message_template.format(**PLACEHOLDER_MAP)
                        if message_template
                        else DEFAULT_BODY,
                        "type": "send-notification",
                        "subject": "Prefect flow run notification",
                        "block_document_id": str(block_document_id),
                    }
                ]

                conn.execute(
                    sa.text(
                        "INSERT INTO automation (name, description, enabled, trigger, actions) VALUES (:name, :description, :enabled, :trigger, :actions)",
                    ),
                    {
                        "name": "Flow Run State Change Notification",
                        "description": "Migrated from a flow run notification policy",
                        "enabled": is_active,
                        "trigger": json.dumps(trigger),
                        "actions": json.dumps(actions),
                    },
                )

                conn.execute(
                    sa.text("DELETE FROM flow_run_notification_policy WHERE id = :id"),
                    {"id": row[0]},
                )

            get_logger().info(
                f"Your {len(rows)} flow run notification policies have been migrated to automations. You can view the created automations in the Prefect UI."
            )

    op.drop_table("flow_run_notification_queue")
    op.drop_table("flow_run_notification_policy")


def downgrade():
    op.create_table(
        "flow_run_notification_queue",
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
        sa.Column(
            "flow_run_notification_policy_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.Column(
            "flow_run_state_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flow_run_notification_queue")),
    )
    op.create_index(
        op.f("ix_flow_run_notification_queue__updated"),
        "flow_run_notification_queue",
        ["updated"],
        unique=False,
    )
    op.create_table(
        "flow_run_notification_policy",
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
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "state_names",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "tags",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("message_template", sa.String(), nullable=True),
        sa.Column(
            "block_document_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_document_id"],
            ["block_document.id"],
            name=op.f(
                "fk_flow_run_notification_policy__block_document_id__block_document"
            ),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flow_run_notification_policy")),
    )
    op.create_index(
        op.f("ix_flow_run_notification_policy__updated"),
        "flow_run_notification_policy",
        ["updated"],
        unique=False,
    )
