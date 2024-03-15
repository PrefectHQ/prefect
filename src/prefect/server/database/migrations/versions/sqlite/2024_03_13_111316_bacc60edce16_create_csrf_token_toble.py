"""Create csrf_token toble

Revision ID: bacc60edce16
Revises: 342220764f0b
Create Date: 2024-03-13 11:13:16.487004

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "bacc60edce16"
down_revision = "342220764f0b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "csrf_token",
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("client", sa.String(), nullable=False),
        sa.Column(
            "expiration",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_csrf_token")),
        sa.UniqueConstraint("client", name=op.f("uq_csrf_token__client")),
    )
    with op.batch_alter_table("csrf_token", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_csrf_token__updated"), ["updated"], unique=False
        )


def downgrade():
    with op.batch_alter_table("csrf_token", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_csrf_token__updated"))

    op.drop_table("csrf_token")
