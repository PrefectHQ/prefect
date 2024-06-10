"""Add `last_polled` to deployment

Revision ID: bfe653bbf62e
Revises: 05ea6f882b1d
Create Date: 2023-10-12 22:45:11.024191

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "bfe653bbf62e"
down_revision = "05ea6f882b1d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "last_polled",
                prefect.server.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("last_polled")
