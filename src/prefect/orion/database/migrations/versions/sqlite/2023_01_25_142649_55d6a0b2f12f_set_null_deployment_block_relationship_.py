"""SET NULL deployment block relationship on delete instead of CASCADE

Revision ID: 55d6a0b2f12f
Revises: bb38729c471a
Create Date: 2023-01-25 14:26:49.264075

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "55d6a0b2f12f"
down_revision = "bb38729c471a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_deployment__storage_document_id__block_document", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_deployment__infrastructure_document_id__block_document",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__infrastructure_document_id__block_document"),
            "block_document",
            ["infrastructure_document_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__storage_document_id__block_document"),
            "block_document",
            ["storage_document_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():

    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_deployment__storage_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            batch_op.f("fk_deployment__infrastructure_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_deployment__infrastructure_document_id__block_document",
            "block_document",
            ["infrastructure_document_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_deployment__storage_document_id__block_document",
            "block_document",
            ["storage_document_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute("PRAGMA foreign_keys=ON")
