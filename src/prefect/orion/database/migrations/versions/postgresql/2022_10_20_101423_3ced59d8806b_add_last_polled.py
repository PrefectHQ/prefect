"""Add last_polled

Revision ID: 3ced59d8806b
Revises: 6d548701edef
Create Date: 2022-10-14 10:14:23.979848

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "3ced59d8806b"
down_revision = "6d548701edef"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "last_polled",
                prefect.orion.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_column("last_polled")
