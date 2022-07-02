"""Add indexes for partial name matches

Revision ID: f65b6ad0b869
Revises: d76326ed0d06
Create Date: 2022-06-04 10:40:48.710626

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "f65b6ad0b869"
down_revision = "d76326ed0d06"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX ix_flow_name_case_insensitive on flow (name COLLATE NOCASE);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_flow_run_name_case_insensitive on flow_run (name COLLATE NOCASE);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_task_run_name_case_insensitive on task_run (name COLLATE NOCASE);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_deployment_name_case_insensitive on deployment (name COLLATE NOCASE);
        """
    )


def downgrade():

    op.execute(
        """
        DROP INDEX ix_flow_name_case_insensitive;
        """
    )
    op.execute(
        """
        DROP INDEX ix_flow_run_name_case_insensitive;
        """
    )
    op.execute(
        """
        DROP INDEX ix_task_run_name_case_insensitive;
        """
    )
    op.execute(
        """
        DROP INDEX ix_deployment_name_case_insensitive;
        """
    )
