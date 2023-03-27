"""Add pull steps column to deployment

Revision ID: 43c94d4c7aa3
Revises: 46bd82c6279a
Create Date: 2023-03-27 13:24:06.669728

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "43c94d4c7aa3"
down_revision = "46bd82c6279a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column(
            "pull_steps",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("deployment", "pull_steps")
