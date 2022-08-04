"""Update deployments to include more information

Revision ID: 88c2112b668f
Revises: f335f9633eec
Create Date: 2022-07-25 13:10:28.849740

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "88c2112b668f"
down_revision = "f335f9633eec"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deployment", sa.Column("manifest_path", sa.String(), nullable=True))
    # any existing deployment is broken by these changes
    # set manifest path to an empty string
    # and turn the schedule off
    op.execute(sa.text("UPDATE deployment SET manifest_path = '';"))
    op.execute(sa.text("UPDATE deployment SET is_schedule_active = False;"))
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
