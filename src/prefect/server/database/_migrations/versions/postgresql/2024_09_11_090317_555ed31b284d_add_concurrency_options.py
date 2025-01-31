"""add concurrency options

Revision ID: 555ed31b284d
Revises: 97429116795e
Create Date: 2024-09-11 09:03:17.744587

"""

import sqlalchemy as sa
from alembic import op

import prefect
from prefect.server.schemas.core import ConcurrencyOptions

# revision identifiers, used by Alembic.
revision = "555ed31b284d"
down_revision = "97429116795e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column(
            "concurrency_options",
            prefect.server.utilities.database.Pydantic(ConcurrencyOptions),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("deployment", "concurrency_options")
