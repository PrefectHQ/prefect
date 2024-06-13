"""Add index on artifact

Revision ID: 46bd82c6279a
Revises: d20618ce678e
Create Date: 2023-03-20 18:56:10.725419

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "46bd82c6279a"
down_revision = "d20618ce678e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX 
        IF NOT EXISTS
        ix_artifact__key_created_desc
        ON artifact (key, created DESC)
        INCLUDE (id, updated, type, task_run_id, flow_run_id)
    """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX 
        IF EXISTS
        ix_artifact__key_created_desc
    """
    )
