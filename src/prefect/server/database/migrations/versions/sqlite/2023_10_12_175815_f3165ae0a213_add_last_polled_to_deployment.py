"""Add `last_polled` to deployment

Revision ID: f3165ae0a213
Revises: 05ea6f882b1d
Create Date: 2023-10-12 17:58:15.326385

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "f3165ae0a213"
down_revision = "05ea6f882b1d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "last_polled",
                prefect.server.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("last_polled")

    op.execute("PRAGMA foreign_keys=ON")
