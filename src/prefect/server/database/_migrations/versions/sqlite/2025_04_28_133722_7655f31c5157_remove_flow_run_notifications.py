"""Remove flow run notifications

Revision ID: 7655f31c5157
Revises: bbca16f6f218
Create Date: 2025-04-28 13:37:22.112876

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

import prefect

# revision identifiers, used by Alembic.
revision = "7655f31c5157"
down_revision = "bbca16f6f218"
branch_labels = None
depends_on = None


def upgrade():
    # Check if there are any rows in flow_run_notification_policy
    conn = op.get_bind()
    result = conn.execute(
        text("SELECT COUNT(*) FROM flow_run_notification_policy")
    ).scalar()

    if result is not None and result > 0:
        raise Exception(
            f"Cannot proceed with migration: Found {result} rows in flow_run_notification_policy table. "
            "Please run `uvx prefect-migrate flow-run-notifications migrate` to migrate your notification policies to automations."
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
        sa.Column("name", sa.String(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flow_run_alert")),
    )
    op.create_index(
        op.f("ix_flow_run_notification_policy__name"),
        "flow_run_notification_policy",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flow_run_notification_policy__updated"),
        "flow_run_notification_policy",
        ["updated"],
        unique=False,
    )
