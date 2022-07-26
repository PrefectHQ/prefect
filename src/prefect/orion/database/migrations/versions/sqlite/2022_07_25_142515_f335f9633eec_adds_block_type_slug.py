"""Adds block type slug

Revision ID: f335f9633eec
Revises: 2fe8ef6a6514
Create Date: 2022-07-25 14:25:15.809720

"""
import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f335f9633eec"
down_revision = "2fe8ef6a6514"
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
    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(), nullable=True))
        batch_op.drop_index("uq_block_type__name")
        batch_op.create_index("uq_block_type__slug", ["slug"], unique=True)

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

    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.alter_column("slug", existing_type=sa.VARCHAR(), nullable=False)


def downgrade():
    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.drop_index("uq_block_type__slug")
        batch_op.create_index("uq_block_type__name", ["name"], unique=False)
        batch_op.drop_column("slug")
