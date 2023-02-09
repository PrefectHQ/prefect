"""Add indexes for partial name matches

Revision ID: 77ebcc9cf355
Revises: cdcb4018dd0e
Create Date: 2022-06-04 10:40:48.710626

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "77ebcc9cf355"
down_revision = "cdcb4018dd0e"
branch_labels = None
depends_on = None


def upgrade():
    # install pg_trgm
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

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

    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
