"""
add flow concurrency limits

Revision ID: 52f08a976090
Revises: 7e65dadba625
Create Date: 2020-04-20 10:28:10.913791

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "52f08a976090"
down_revision = "7e65dadba625"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        -- Table Definition ----------------------------------------------

        CREATE TABLE flow_concurrency_limit (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            updated timestamp with time zone NOT NULL DEFAULT now(),
            name character varying NOT NULL UNIQUE,
            description text,
            "limit" integer NOT NULL
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_flow_concurrency_name ON flow_concurrency_limit(name text_ops);

        """
    )
    op.execute(
        """
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON public.flow_concurrency_limit
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE flow_concurrency_limit CASCADE;
        """
    )
