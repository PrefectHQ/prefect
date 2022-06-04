"""Add indexes for partial name matches

Revision ID: f65b6ad0b869
Revises: d76326ed0d06
Create Date: 2022-06-04 10:40:48.710626

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "f65b6ad0b869"
down_revision = "d76326ed0d06"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY 
            trgm_ix_flow_name 
            ON flow USING gin (name gin_trgm_ops);
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY 
            trgm_ix_flow_run_name 
            ON flow_run USING gin (name gin_trgm_ops);
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY 
            trgm_ix_task_run_name 
            ON task_run USING gin (name gin_trgm_ops);
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY 
            trgm_ix_deployment_name 
            ON deployment USING gin (name gin_trgm_ops);
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY trgm_ix_flow_name;
            """
        )
        op.execute(
            """
            DROP INDEX CONCURRENTLY trgm_ix_flow_run_name;
            """
        )
        op.execute(
            """
            DROP INDEX CONCURRENTLY trgm_ix_task_run_name;
            """
        )
        op.execute(
            """
            DROP INDEX CONCURRENTLY trgm_ix_deployment_name;
            """
        )
