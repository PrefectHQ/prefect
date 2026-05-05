"""Add CHECK constraint preventing block_document_reference self-references

Revision ID: 2095de406cbe
Revises: 4dfa692e02a7
Create Date: 2026-05-05 00:00:00.000000

Enforces parent_block_document_id != reference_block_document_id at the
database layer. Any pre-existing rows that would violate the constraint
are deleted first so the migration is installable on existing databases.

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "2095de406cbe"
down_revision = "4dfa692e02a7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM block_document_reference
        WHERE parent_block_document_id = reference_block_document_id
        """
    )
    with op.batch_alter_table("block_document_reference") as batch_op:
        batch_op.create_check_constraint(
            "ck_block_document_reference__no_self_reference",
            "parent_block_document_id != reference_block_document_id",
        )


def downgrade():
    with op.batch_alter_table("block_document_reference") as batch_op:
        batch_op.drop_constraint(
            "ck_block_document_reference__no_self_reference",
            type_="check",
        )
