"""Create csrf_token toble

Revision ID: 7a653837d9ba
Revises: 121699507574
Create Date: 2024-03-13 11:12:15.491121

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "7a653837d9ba"
down_revision = "121699507574"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "csrf_token",
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("client", sa.String(), nullable=False),
        sa.Column(
            "expiration",
            prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_csrf_token")),
        sa.UniqueConstraint("client", name=op.f("uq_csrf_token__client")),
    )
    op.create_index(
        op.f("ix_csrf_token__updated"), "csrf_token", ["updated"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_csrf_token__updated"), table_name="csrf_token")
    op.drop_table("csrf_token")
