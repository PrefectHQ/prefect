"""Remove agent table

Revision ID: 8a4a6d7a6586
Revises: 3ced59d8806b
Create Date: 2022-10-14 10:39:32.969831

"""
import sqlalchemy as sa
from alembic import op

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
            sa.CHAR(length=36),
            server_default=sa.text(
                "(((\n        lower(hex(randomblob(4))) \n        || '-' \n        || lower(hex(randomblob(2))) \n        || '-4' \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || substr('89ab',abs(random()) % 4 + 1, 1) \n        || substr(lower(hex(randomblob(2))),2) \n        || '-' \n        || lower(hex(randomblob(6)))\n    )))"
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
        sa.Column(
            "last_activity_time",
            sa.DATETIME(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("work_queue_id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_queue_id"],
            ["work_queue.id"],
            name="fk_agent__work_queue_id__work_queue",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent"),
        sa.UniqueConstraint("name", name="uq_agent__name"),
    )
    with op.batch_alter_table("agent", schema=None) as batch_op:
        batch_op.create_index(
            "ix_agent__work_queue_id", ["work_queue_id"], unique=False
        )
        batch_op.create_index("ix_agent__updated", ["updated"], unique=False)
