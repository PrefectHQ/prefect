"""change deployment concurrency limit type

Revision ID: 3b4bc664921d
Revises: 97429116795e
Create Date: 2024-09-06 17:08:43.236854

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "3b4bc664921d"
down_revision = "97429116795e"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "deployment",
        "concurrency_limit",
        existing_type=sa.INTEGER(),
        type_=prefect.server.utilities.database.Pydantic(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "deployment",
        "concurrency_limit",
        existing_type=prefect.server.utilities.database.Pydantic(),
        type_=sa.INTEGER(),
        existing_nullable=True,
    )
