"""Add index for querying artifacts

Revision ID: 422f8ba9541d
Revises: b9aafc3ab936
Create Date: 2023-03-20 19:42:04.862363

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "422f8ba9541d"
down_revision = "b9aafc3ab936"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_artifact__key_created_desc
        ON artifact_collection (key, created DESC)
        """
    )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.execute(
        """
        DROP INDEX IF EXISTS
        ix_artifact__key_created_desc
        """
    )

    op.execute("PRAGMA foreign_keys=ON")
