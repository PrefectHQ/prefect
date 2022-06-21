"""Rename Block to BlockDocument and BlockSpec to BlockSchema

Revision ID: fd966d4ad99c
Revises: 71a57ec351d1
Create Date: 2022-04-19 11:48:31.878028

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "fd966d4ad99c"
down_revision = "db6bde582447"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("block_spec", "block_schema")
    op.rename_table("block", "block_document")

    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.drop_index("ix_block__is_default_storage_block")
        batch_op.drop_index("ix_block__name")
        batch_op.drop_index("ix_block__updated")
        batch_op.drop_index("uq_block__spec_id_name")
        batch_op.alter_column("block_spec_id", new_column_name="block_schema_id")
        batch_op.alter_column(
            "is_default_storage_block",
            new_column_name="is_default_storage_block_document",
        )
        batch_op.drop_constraint("fk_block__block_spec_id__block_spec")
        batch_op.drop_constraint("pk_block_data")

    with op.batch_alter_table("block_document", schema=None) as batch_op:

        batch_op.create_index(
            batch_op.f("ix_block_document__is_default_storage_block_document"),
            ["is_default_storage_block_document"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_block_document__name"), ["name"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_block_document__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            "uq_block__schema_id_name", ["block_schema_id", "name"], unique=True
        )

    with op.batch_alter_table("block_schema", schema=None) as batch_op:
        batch_op.drop_index("ix_block_spec__type")
        batch_op.drop_index("ix_block_spec__updated")
        batch_op.drop_index("uq_block_spec__name_version")
        batch_op.create_index("ix_block_schema__type", ["type"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_block_schema__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            "uq_block_schema__name_version", ["name", "version"], unique=True
        )
        batch_op.drop_constraint("pk_block_spec")
        batch_op.create_primary_key("pk_block_schema", ["id"])

    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.create_primary_key("pk_block_document", ["id"])
        batch_op.create_foreign_key(
            batch_op.f("fk_block__block_schema_id__block_schema"),
            "block_schema",
            ["block_schema_id"],
            ["id"],
            ondelete="cascade",
        )


def downgrade():
    op.rename_table("block_schema", "block_spec")
    op.rename_table("block_document", "block")

    with op.batch_alter_table("block", schema=None) as batch_op:
        batch_op.drop_index("ix_block_document__is_default_storage_block_document")
        batch_op.drop_index("ix_block_document__name")
        batch_op.drop_index("ix_block_document__updated")
        batch_op.drop_index("uq_block__schema_id_name")
        batch_op.drop_constraint("fk_block__block_schema_id__block_schema")
        batch_op.drop_constraint("pk_block_document")

    with op.batch_alter_table("block", schema=None) as batch_op:
        batch_op.alter_column("block_schema_id", new_column_name="block_spec_id")
        batch_op.alter_column(
            "is_default_storage_block_document",
            new_column_name="is_default_storage_block",
        )

    with op.batch_alter_table("block", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_block__is_default_storage_block"),
            ["is_default_storage_block"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_block__name"), ["name"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_block__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            "uq_block__spec_id_name", ["block_spec_id", "name"], unique=True
        )

    with op.batch_alter_table("block_spec", schema=None) as batch_op:
        batch_op.drop_index("ix_block_schema__type")
        batch_op.drop_index("ix_block_schema__updated")
        batch_op.drop_index("uq_block_schema__name_version")
        batch_op.create_index("ix_block_spec__type", ["type"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_block_spec__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            "uq_block_spec__name_version", ["name", "version"], unique=True
        )
        batch_op.drop_constraint("pk_block_schema")
        batch_op.create_primary_key("pk_block_spec", ["id"])

    with op.batch_alter_table("block", schema=None) as batch_op:
        batch_op.create_primary_key("pk_block_data", ["id"])
        batch_op.create_foreign_key(
            batch_op.f("fk_block__block_spec_id__block_spec"),
            "block_spec",
            ["block_spec_id"],
            ["id"],
            ondelete="cascade",
        )
