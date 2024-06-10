"""Clean up work queue migration

Revision ID: 2a88656f4a23
Revises: f98ae6d8e2cc
Create Date: 2023-01-31 13:30:52.172981

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "2a88656f4a23"
down_revision = "f98ae6d8e2cc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("work_pool_queue", schema=None) as batch_op:
        batch_op.drop_index("ix_work_pool_queue__updated")
        batch_op.drop_index("ix_work_pool_queue__work_pool_id")
        batch_op.drop_index("ix_work_pool_queue__work_pool_id_priority")

    op.drop_table("work_pool_queue")

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column(
            "work_pool_id", existing_type=sa.CHAR(length=36), nullable=False
        )


def downgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column(
            "work_pool_id", existing_type=sa.CHAR(length=36), nullable=True
        )

    op.create_table(
        "work_pool_queue",
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
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "work_pool_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_pool_id"],
            ["work_pool.id"],
            name=op.f("fk_work_pool_queue__work_pool_id__work_pool"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_pool_queue")),
        sa.UniqueConstraint(
            "work_pool_id",
            "name",
            name=op.f("uq_work_pool_queue__work_pool_id_name"),
        ),
    )
    with op.batch_alter_table("work_pool_queue", schema=None) as batch_op:
        batch_op.create_index(
            "ix_work_pool_queue__work_pool_id_priority",
            ["work_pool_id", "priority"],
            unique=False,
        )
        batch_op.create_index(
            "ix_work_pool_queue__work_pool_id", ["work_pool_id"], unique=False
        )
        batch_op.create_index("ix_work_pool_queue__updated", ["updated"], unique=False)
