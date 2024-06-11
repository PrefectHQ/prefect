"""add_index_on_log

Revision ID: 553920ec20e9
Revises: 422f8ba9541d
Create Date: 2023-04-04 11:51:50.514999

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "553920ec20e9"
down_revision = "422f8ba9541d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("log", schema=None) as batch_op:
        batch_op.create_index(
            "ix_log__flow_run_id_timestamp", ["flow_run_id", "timestamp"], unique=False
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("log", schema=None) as batch_op:
        batch_op.drop_index("ix_log__flow_run_id_timestamp")

    op.execute("PRAGMA foreign_keys=ON")
