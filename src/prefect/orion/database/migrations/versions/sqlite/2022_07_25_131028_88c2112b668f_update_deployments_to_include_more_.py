"""Update deployments to include more information

Revision ID: 88c2112b668f
Revises: 2fe8ef6a6514
Create Date: 2022-07-25 13:10:28.849740

"""
from alembic import op
import sqlalchemy as sa
import prefect


# revision identifiers, used by Alembic.
revision = "88c2112b668f"
down_revision = "2fe8ef6a6514"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deployment", sa.Column("manifest_path", sa.String(), nullable=True))
    op.add_column(
        "deployment",
        sa.Column(
            "parameter_openapi_schema",
            prefect.orion.utilities.database.JSON(),
            nullable=True,
        ),
    )

    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "storage_document_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__storage_document_id__block_document"),
            "block_document",
            ["storage_document_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("manifest_path")
        batch_op.drop_column("parameter_openapi_schema")
        batch_op.drop_constraint(
            batch_op.f("fk_deployment__storage_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.drop_column("storage_document_id")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_flow_run__storage_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.drop_column("storage_document_id")
