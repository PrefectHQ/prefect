"""add_index_on_log

Revision ID: 3bf47e3ce2dd
Revises: 46bd82c6279a
Create Date: 2023-04-04 13:25:34.694078

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "3bf47e3ce2dd"
down_revision = "46bd82c6279a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_log__flow_run_id_timestamp",
        "log",
        ["flow_run_id", "timestamp"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_log__flow_run_id_timestamp", table_name="log")
