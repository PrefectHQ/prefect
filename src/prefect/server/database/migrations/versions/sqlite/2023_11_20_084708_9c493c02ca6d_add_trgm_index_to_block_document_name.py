"""Add trgm index to block_document.name

Revision ID: 9c493c02ca6d
Revises: 22ef3915ccd8
Create Date: 2023-11-20 08:47:08.929487

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9c493c02ca6d"
down_revision = "22ef3915ccd8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX ix_block_document_name_case_insensitive on block_document (name COLLATE NOCASE);
        """
    )


def downgrade():
    op.execute("DROP INDEX ix_block_document_name_case_insensitive;")
