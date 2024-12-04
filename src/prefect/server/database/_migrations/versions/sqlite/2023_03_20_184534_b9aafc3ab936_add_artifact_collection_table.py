"""Adds artifact_collection table

Revision ID: b9aafc3ab936
Revises: 1d7441c031d0
Create Date: 2023-03-20 18:45:34.438841

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "b9aafc3ab936"
down_revision = "1d7441c031d0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.create_table(
        "artifact_collection",
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
        sa.Column("key", sa.String(), nullable=False),
        sa.Column(
            "latest_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_collection")),
        sa.UniqueConstraint("key", name=op.f("uq_artifact_collection__key")),
    )
    op.create_index(
        op.f("ix_artifact_collection__key_latest_id"),
        "artifact_collection",
        ["key", "latest_id"],
    )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.drop_index(
        op.f("ix_artifact_collection__key_latest_id"), table_name="artifact_collection"
    )

    op.drop_table("artifact_collection")

    op.execute("PRAGMA foreign_keys=ON")
