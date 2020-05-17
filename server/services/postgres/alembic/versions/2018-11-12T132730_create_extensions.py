# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

"""create extensions

Revision ID: 723da8052cbd
Revises:
Create Date: 2020-03-18 09:46:06.168069

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "723da8052cbd"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        CREATE EXTENSION IF NOT EXISTS "pg_trgm";
        """
    )


def downgrade():
    pass
