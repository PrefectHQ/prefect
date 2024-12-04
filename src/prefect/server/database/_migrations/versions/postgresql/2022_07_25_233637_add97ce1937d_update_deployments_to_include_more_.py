"""Update deployments to include more information

Revision ID: add97ce1937d
Revises: 4ff2f2bf81f4
Create Date: 2022-07-25 13:36:37.811822

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "add97ce1937d"
down_revision = "4ff2f2bf81f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deployment", sa.Column("description", sa.TEXT(), nullable=True))
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
            prefect.server.utilities.database.JSON(),
            nullable=True,
        ),
    )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "storage_document_id",
                prefect.server.utilities.database.UUID(),
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


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("manifest_path")
        batch_op.drop_column("description")
        batch_op.drop_column("parameter_openapi_schema")
        batch_op.drop_constraint(
            batch_op.f("fk_deployment__storage_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.drop_column("storage_document_id")
