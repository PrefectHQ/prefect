"""Adds block schema version

Revision ID: e757138e954a
Revises: 575634b7acd4
Create Date: 2022-08-18 10:25:27.189680

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e757138e954a"
down_revision = "575634b7acd4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("block_schema", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "version", sa.String(), server_default="non-versioned", nullable=False
            )
        )
        batch_op.drop_index("uq_block_schema__checksum")
        batch_op.create_index(
            "uq_block_schema__checksum_version", ["checksum", "version"], unique=True
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    with op.batch_alter_table("block_schema", schema=None) as batch_op:
        batch_op.drop_index("uq_block_schema__checksum_version")
        batch_op.create_index("uq_block_schema__checksum", ["checksum"], unique=False)
        batch_op.drop_column("version")
