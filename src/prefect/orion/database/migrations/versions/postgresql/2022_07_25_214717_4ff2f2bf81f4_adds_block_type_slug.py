"""Adds block type slug

Revision ID: 4ff2f2bf81f4
Revises: e085c9cbf8ce
Create Date: 2022-07-25 21:47:17.992159

"""
import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ff2f2bf81f4"
down_revision = "e085c9cbf8ce"
branch_labels = None
depends_on = None

REMOVE_NON_ALPHA_NUMBER = re.compile(r"[^\w\s-]")
CONVERT_TO_DASHES = re.compile(r"[\s_-]+")
REMOVE_LEAD_TRAILING_DASHES = re.compile(r"^-+|-+$")


def slugify(string: str):
    string = string.lower().strip()
    # Remove any non alphanumeric characters
    string = re.sub(REMOVE_NON_ALPHA_NUMBER, "", string)
    # Convert spaces and underscores to dashes
    string = re.sub(CONVERT_TO_DASHES, "-", string)
    # Remove leading and trailing dashes
    string = re.sub(REMOVE_LEAD_TRAILING_DASHES, "", string)
    return string


def upgrade():
    op.add_column("block_type", sa.Column("slug", sa.String(), nullable=True))
    op.drop_index("uq_block_type__name", table_name="block_type")
    op.create_index("uq_block_type__slug", "block_type", ["slug"], unique=True)

    # Add slugs to existing block types
    connection = op.get_bind()
    meta_data = sa.MetaData(bind=connection)
    meta_data.reflect()
    BLOCK_TYPE = meta_data.tables["block_type"]

    block_types_result = connection.execute(
        sa.select([BLOCK_TYPE.c.id, BLOCK_TYPE.c.name])
    ).all()
    for id, name in block_types_result:
        connection.execute(
            sa.update(BLOCK_TYPE)
            .where(BLOCK_TYPE.c.id == id)
            .values(slug=slugify(name))
        )

    op.alter_column("block_type", "slug", nullable=False)


def downgrade():
    op.drop_index("uq_block_type__slug", table_name="block_type")
    op.create_index("uq_block_type__name", "block_type", ["name"], unique=False)
    op.drop_column("block_type", "slug")
