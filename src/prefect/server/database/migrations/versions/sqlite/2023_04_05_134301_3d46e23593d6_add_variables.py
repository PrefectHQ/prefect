"""add_variables

Revision ID: 3d46e23593d6
Revises: 553920ec20e9
Create Date: 2023-04-05 13:43:01.901404

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "3d46e23593d6"
down_revision = "340f457b315f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.create_table(
        "variable",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column(
            "tags",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_variable")),
        sa.UniqueConstraint("name", name=op.f("uq_variable__name")),
    )
    with op.batch_alter_table("variable", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_variable__updated"), ["updated"], unique=False
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("variable", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_variable__updated"))

    op.drop_table("variable")

    op.execute("PRAGMA foreign_keys=ON")
