"""Clean up work queue migration

Revision ID: 2a88656f4a23
Revises: f98ae6d8e2cc
Create Date: 2023-01-31 13:30:52.172981

"""
import sqlalchemy as sa
from alembic import op

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
            sa.CHAR(length=36),
            server_default=sa.text(
                "(((\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )))"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            sa.DATETIME(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DATETIME(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("description", sa.VARCHAR(), nullable=True),
        sa.Column(
            "is_paused", sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=False
        ),
        sa.Column("concurrency_limit", sa.INTEGER(), nullable=True),
        sa.Column("priority", sa.INTEGER(), nullable=False),
        sa.Column("work_pool_id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_pool_id"],
            ["work_pool.id"],
            name="fk_work_pool_queue__work_pool_id__work_pool",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_work_pool_queue"),
        sa.UniqueConstraint(
            "work_pool_id", "name", name="uq_work_pool_queue__work_pool_id_name"
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
