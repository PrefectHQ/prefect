"""change deployment concurrency limit type

Revision ID: 78bf051472eb
Revises: f93e1439f022
Create Date: 2024-09-06 16:32:02.584968

"""
import sqlalchemy as sa
from alembic import op

import prefect
from prefect.server.schemas.core import ConcurrencyOptions

# revision identifiers, used by Alembic.
revision = "78bf051472eb"
down_revision = "f93e1439f022"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.alter_column(
            "concurrency_limit",
            existing_type=sa.INTEGER(),
            type_=prefect.server.utilities.database.Pydantic(ConcurrencyOptions),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.alter_column(
            "concurrency_limit",
            existing_type=prefect.server.utilities.database.Pydantic(
                ConcurrencyOptions
            ),
            type_=sa.INTEGER(),
            existing_nullable=True,
        )
