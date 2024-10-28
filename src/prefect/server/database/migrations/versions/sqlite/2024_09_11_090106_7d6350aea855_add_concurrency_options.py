"""add concurrency options

Revision ID: 7d6350aea855
Revises: f93e1439f022
Create Date: 2024-09-11 09:01:06.678866

"""
import sqlalchemy as sa
from alembic import op

import prefect
from prefect.server.schemas.core import ConcurrencyOptions

# revision identifiers, used by Alembic.
revision = "7d6350aea855"
down_revision = "f93e1439f022"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "concurrency_options",
                prefect.server.utilities.database.Pydantic(ConcurrencyOptions),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("concurrency_options")
