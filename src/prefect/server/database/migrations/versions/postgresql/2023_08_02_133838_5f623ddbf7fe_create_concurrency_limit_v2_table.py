"""Create concurrency_limit_v2 table

Revision ID: 5f623ddbf7fe
Revises: 15f5083c16bd
Create Date: 2023-08-02 13:38:38.691551

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "5f623ddbf7fe"
down_revision = "15f5083c16bd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "concurrency_limit_v2",
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
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("active_slots", sa.Integer(), nullable=False),
        sa.Column("denied_slots", sa.Integer(), nullable=False),
        sa.Column("slot_decay_per_second", sa.Float(), nullable=True),
        sa.Column("avg_slot_occupancy_seconds", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concurrency_limit_v2")),
        sa.UniqueConstraint("name", name=op.f("uq_concurrency_limit_v2__name")),
    )
    op.create_index(
        op.f("ix_concurrency_limit_v2__updated"),
        "concurrency_limit_v2",
        ["updated"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_concurrency_limit_v2__updated"), table_name="concurrency_limit_v2"
    )
    op.drop_table("concurrency_limit_v2")
