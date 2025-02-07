"""Add slug column to deployment_schedule

Revision ID: 07ecde74d74d
Revises: 67f886da208e
Create Date: 2025-02-05 15:24:31.503016

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "07ecde74d74d"
down_revision = "67f886da208e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("slug", sa.String, nullable=True),
        )
        batch_op.create_index(
            "ix_deployment_schedule__slug",
            ["slug"],
            unique=False,
            if_not_exists=True,
        )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        ix_deployment_schedule__deployment_id__slug
        ON deployment_schedule(deployment_id, slug)
        WHERE slug IS NOT NULL;
        """
    )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployment_schedule__deployment_id__slug"))
        batch_op.drop_index("ix_deployment_schedule__slug")
        batch_op.drop_column("slug")
    op.execute("PRAGMA foreign_keys=ON")
