"""
fix log default timestamp

Revision ID: 7e65dadba625
Revises: 6b0389a57a0a
Create Date: 2020-03-30 16:04:56.034089

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "7e65dadba625"
down_revision = "6b0389a57a0a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE log ALTER COLUMN timestamp DROP DEFAULT;
        ALTER TABLE log ALTER COLUMN timestamp SET DEFAULT clock_timestamp();
        """
    )


def downgrade():

    op.execute(
        """
        ALTER TABLE log ALTER COLUMN timestamp DROP DEFAULT;
        ALTER TABLE log ALTER COLUMN timestamp SET DEFAULT '2020-03-18 13:42:43.118776+00'::timestamp with time zone;
        """
    )
