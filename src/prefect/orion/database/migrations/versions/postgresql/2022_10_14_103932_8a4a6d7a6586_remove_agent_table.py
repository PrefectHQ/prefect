"""Remove agent table

Revision ID: 8a4a6d7a6586
Revises: 3ced59d8806b
Create Date: 2022-10-14 10:39:32.969831

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "8a4a6d7a6586"
down_revision = "3ced59d8806b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agent", schema=None) as batch_op:
        batch_op.drop_index("ix_agent__updated")
        batch_op.drop_index("ix_agent__work_queue_id")

    op.drop_table("agent")


def downgrade():
    op.create_table(
        "agent",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_activity_time",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "work_queue_id", prefect.orion.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_queue_id"],
            ["work_queue.id"],
            name=op.f("fk_agent__work_queue_id__work_queue"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent")),
        sa.UniqueConstraint("name", name=op.f("uq_agent__name")),
    )
    op.create_index(op.f("ix_agent__updated"), "agent", ["updated"], unique=False)
    op.create_index(
        op.f("ix_agent__work_queue_id"), "agent", ["work_queue_id"], unique=False
    )
