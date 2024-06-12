"""Adds block type slug

Revision ID: 4ff2f2bf81f4
Revises: e085c9cbf8ce
Create Date: 2022-07-25 21:47:17.992159

"""

import sqlalchemy as sa
from alembic import op

from prefect.blocks.core import Block
from prefect.utilities.slugify import slugify

# revision identifiers, used by Alembic.
revision = "4ff2f2bf81f4"
down_revision = "e085c9cbf8ce"
branch_labels = None
depends_on = None


def replace_name_with_slug(fields):
    if isinstance(fields, list):
        return [replace_name_with_slug(x) for x in fields]
    if isinstance(fields, dict):
        new_dict = {}
        for k, v in fields.items():
            if k == "block_type_name":
                new_dict["block_type_slug"] = slugify(v)
            else:
                new_dict[k] = v
        return new_dict
    return fields


def upgrade():
    op.add_column("block_type", sa.Column("slug", sa.String(), nullable=True))
    op.drop_index("uq_block_type__name", table_name="block_type")
    op.create_index("uq_block_type__slug", "block_type", ["slug"], unique=True)

    # Add slugs to existing block types
    connection = op.get_bind()
    meta_data = sa.MetaData()
    meta_data.reflect(connection)
    BLOCK_TYPE = meta_data.tables["block_type"]
    BLOCK_SCHEMA = meta_data.tables["block_schema"]

    block_types_result = connection.execute(
        sa.select(BLOCK_TYPE.c.id, BLOCK_TYPE.c.name)
    ).all()
    for block_type_id, block_type_name in block_types_result:
        connection.execute(
            sa.update(BLOCK_TYPE)
            .where(BLOCK_TYPE.c.id == block_type_id)
            .values(slug=slugify(block_type_name))
        )

        block_schemas_result = connection.execute(
            sa.select(BLOCK_SCHEMA.c.id, BLOCK_SCHEMA.c.fields).where(
                BLOCK_SCHEMA.c.block_type_id == block_type_id
            )
        ).all()
        for block_schema_id, block_schema_fields in block_schemas_result:
            new_fields = replace_name_with_slug(block_schema_fields)
            connection.execute(
                sa.update(BLOCK_SCHEMA)
                .where(BLOCK_SCHEMA.c.id == block_schema_id)
                .values(
                    fields=replace_name_with_slug(block_schema_fields),
                    checksum=Block._calculate_schema_checksum(new_fields),
                )
            )

    op.alter_column("block_type", "slug", nullable=False)


def downgrade():
    op.drop_index("uq_block_type__slug", table_name="block_type")
    op.create_index("uq_block_type__name", "block_type", ["name"], unique=False)
    op.drop_column("block_type", "slug")
