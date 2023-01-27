"""Adds block schema version

Revision ID: 2d5e000696f1
Revises: 77eb737fc759
Create Date: 2022-08-18 10:28:04.449256

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2d5e000696f1"
down_revision = "77eb737fc759"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "block_schema",
        sa.Column(
            "version", sa.String(), server_default="non-versioned", nullable=False
        ),
    )
    op.drop_index("uq_block_schema__checksum", table_name="block_schema")
    op.create_index(
        "uq_block_schema__checksum_version",
        "block_schema",
        ["checksum", "version"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_block_schema__checksum_version", table_name="block_schema")
    op.create_index(
        "uq_block_schema__checksum", "block_schema", ["checksum"], unique=False
    )
    op.drop_column("block_schema", "version")
