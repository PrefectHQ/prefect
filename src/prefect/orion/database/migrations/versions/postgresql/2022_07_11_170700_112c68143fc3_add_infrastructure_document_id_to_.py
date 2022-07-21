"""Add infrastructure document id to deployments

Revision ID: 112c68143fc3
Revises: e905fd199258
Create Date: 2022-07-11 17:07:00.994735

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "112c68143fc3"
down_revision = "e905fd199258"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column(
            "infrastructure_document_id",
            prefect.orion.utilities.database.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_deployment__infrastructure_document_id__block_document"),
        "deployment",
        "block_document",
        ["infrastructure_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "flow_run",
        sa.Column(
            "infrastructure_document_id",
            prefect.orion.utilities.database.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_flow_run__infrastructure_document_id__block_document"),
        "flow_run",
        "block_document",
        ["infrastructure_document_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        op.f("fk_flow_run__infrastructure_document_id__block_document"),
        "flow_run",
        type_="foreignkey",
    )
    op.drop_column("flow_run", "infrastructure_document_id")
    op.drop_constraint(
        op.f("fk_deployment__infrastructure_document_id__block_document"),
        "deployment",
        type_="foreignkey",
    )
    op.drop_column("deployment", "infrastructure_document_id")
