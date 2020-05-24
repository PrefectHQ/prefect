# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Add updated trigger to all tables

Revision ID: 6b0389a57a0a
Revises: 8666a0ceb70e
Create Date: 2020-03-18 13:14:41.403022

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "6b0389a57a0a"
down_revision = "8666a0ceb70e"
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table in [
        "edge",
        "flow",
        "flow_run",
        "flow_run_state",
        "log",
        "schedule",
        "task",
        "task_run",
        "task_run_state",
    ]:

        if "." in table:
            schema, table = table.split(".")
        else:
            schema = "public"
        op.execute(
            f"""
            CREATE TRIGGER update_timestamp
            BEFORE UPDATE ON {schema}."{table}"
            FOR EACH ROW
            EXECUTE PROCEDURE set_updated_timestamp();
            """
        )


def downgrade():
    op.execute(
        """
        DROP FUNCTION set_updated_timestamp CASCADE;
        """
    )
