"""SET NULL deployment block relationship on delete instead of CASCADE

Revision ID: 12caf319f245
Revises: d481d5058a19
Create Date: 2023-01-25 14:29:39.128803

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "12caf319f245"
down_revision = "d481d5058a19"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "fk_deployment__storage_document_id__block_document",
        "deployment",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_deployment__infrastructure_document_id__block_document",
        "deployment",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_deployment__infrastructure_document_id__block_document"),
        "deployment",
        "block_document",
        ["infrastructure_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_deployment__storage_document_id__block_document"),
        "deployment",
        "block_document",
        ["storage_document_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        op.f("fk_deployment__storage_document_id__block_document"),
        "deployment",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_deployment__infrastructure_document_id__block_document"),
        "deployment",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_deployment__infrastructure_document_id__block_document",
        "deployment",
        "block_document",
        ["infrastructure_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_deployment__storage_document_id__block_document",
        "deployment",
        "block_document",
        ["storage_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
