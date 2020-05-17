# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""set utc timezone

Revision ID: 2f249ccdcba7
Revises: 723da8052cbd
Create Date: 2020-03-18 09:46:06.168069

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2f249ccdcba7"
down_revision = "723da8052cbd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        SET TIME ZONE 'UTC';
        """
    )


def downgrade():
    pass
