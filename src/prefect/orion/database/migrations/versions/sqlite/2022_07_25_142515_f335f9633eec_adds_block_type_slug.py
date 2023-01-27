"""Adds block type slug

Revision ID: f335f9633eec
Revises: 2fe8ef6a6514
Create Date: 2022-07-25 14:25:15.809720

"""
import sqlalchemy as sa
from alembic import op

from prefect.blocks.core import Block
from prefect.utilities.slugify import slugify

# revision identifiers, used by Alembic.
revision = "f335f9633eec"
down_revision = "2fe8ef6a6514"
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
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(), nullable=True))
        batch_op.drop_index("uq_block_type__name")
        batch_op.create_index("uq_block_type__slug", ["slug"], unique=True)

    # Add slugs to existing block types
    connection = op.get_bind()
    meta_data = sa.MetaData(bind=connection)
    meta_data.reflect()
    BLOCK_TYPE = meta_data.tables["block_type"]
    BLOCK_SCHEMA = meta_data.tables["block_schema"]

    block_types_result = connection.execute(
        sa.select([BLOCK_TYPE.c.id, BLOCK_TYPE.c.name])
    ).all()
    for block_type_id, block_type_name in block_types_result:
        connection.execute(
            sa.update(BLOCK_TYPE)
            .where(BLOCK_TYPE.c.id == block_type_id)
            .values(slug=slugify(block_type_name))
        )

        block_schemas_result = connection.execute(
            sa.select([BLOCK_SCHEMA.c.id, BLOCK_SCHEMA.c.fields]).where(
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

    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.alter_column("slug", existing_type=sa.VARCHAR(), nullable=False)

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    with op.batch_alter_table("block_type", schema=None) as batch_op:
        batch_op.drop_index("uq_block_type__slug")
        batch_op.create_index("uq_block_type__name", ["name"], unique=False)
        batch_op.drop_column("slug")
