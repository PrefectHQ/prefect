"""add_variables

Revision ID: 310dda75f561
Revises: 3bf47e3ce2dd
Create Date: 2023-04-05 13:45:20.470247

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "310dda75f561"
down_revision = "43c94d4c7aa3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "variable",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column(
            "tags",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_variable")),
        sa.UniqueConstraint("name", name=op.f("uq_variable__name")),
    )
    op.create_index(op.f("ix_variable__updated"), "variable", ["updated"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_variable__updated"), table_name="variable")
    op.drop_table("variable")
