"""Add SQLite covering indexes for observed state discovery.

Revision ID: 27d8f4e1a6c9
Revises: 8f5eda7c1dd7
Create Date: 2026-10-20 00:00:00.000000
"""

from alembic import op

revision = "27d8f4e1a6c9"
down_revision = "8f5eda7c1dd7"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("flow_run_state", "task_run_state"):
        op.create_index(
            f"ix_{table}__type_name_timestamp", table, ["type", "name", "timestamp"]
        )


def downgrade():
    for table in ("flow_run_state", "task_run_state"):
        op.drop_index(f"ix_{table}__type_name_timestamp", table_name=table)
