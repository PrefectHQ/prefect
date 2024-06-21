"""Add infrastructure block id to deployments

Revision ID: 638cbcc2a158
Revises: 061c7e518b40
Create Date: 2022-07-11 11:33:14.404779

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "638cbcc2a158"
down_revision = "061c7e518b40"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "infrastructure_document_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__infrastructure_document_id__block_document"),
            "block_document",
            ["infrastructure_document_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute("PRAGMA foreign_keys=ON")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "infrastructure_document_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run__infrastructure_document_id__block_document"),
            "block_document",
            ["infrastructure_document_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_deployment__infrastructure_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.drop_column("infrastructure_document_id")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_flow_run__infrastructure_document_id__block_document"),
            type_="foreignkey",
        )
        batch_op.drop_column("infrastructure_document_id")
