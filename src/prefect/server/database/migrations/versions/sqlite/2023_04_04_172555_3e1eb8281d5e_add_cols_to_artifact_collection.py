"""Add cols to artifact_collection

Revision ID: 3e1eb8281d5e
Revises: 553920ec20e9
Create Date: 2023-04-04 17:25:55.589739

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "3e1eb8281d5e"
down_revision = "553920ec20e9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("artifact_collection", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_run_id", prefect.server.utilities.database.UUID(), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "flow_run_id", prefect.server.utilities.database.UUID(), nullable=True
            )
        )
        batch_op.add_column(sa.Column("type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("data", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("description", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("metadata_", sa.JSON(), nullable=True))

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("artifact_collection", schema=None) as batch_op:
        batch_op.drop_column("metadata_")
        batch_op.drop_column("description")
        batch_op.drop_column("data")
        batch_op.drop_column("type")
        batch_op.drop_column("flow_run_id")
        batch_op.drop_column("task_run_id")

    op.execute("PRAGMA foreign_keys=ON")
