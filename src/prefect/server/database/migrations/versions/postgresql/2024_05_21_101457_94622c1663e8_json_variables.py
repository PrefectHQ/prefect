"""json_variables

Revision ID: 94622c1663e8
Revises: b23c83a12cb4
Create Date: 2024-05-21 10:14:57.246286

"""

import json

import sqlalchemy as sa
from alembic import op

from prefect.server.utilities.database import JSON

# revision identifiers, used by Alembic.
revision = "94622c1663e8"
down_revision = "b23c83a12cb4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("variable", sa.Column("json_value", JSON, nullable=True))

    conn = op.get_bind()

    result = conn.execute(sa.text("SELECT id, value FROM variable"))
    rows = result.fetchall()

    for variable_id, value in rows:
        # these values need to be json compatible strings
        json_value = json.dumps(value)
        conn.execute(
            sa.text("UPDATE variable SET json_value = :json_value WHERE id = :id"),
            {"json_value": json_value, "id": variable_id},
        )

    op.drop_column("variable", "value")
    op.alter_column("variable", "json_value", new_column_name="value")


def downgrade():
    op.add_column("variable", sa.Column("string_value", sa.String, nullable=True))

    conn = op.get_bind()

    result = conn.execute(sa.text("SELECT id, value FROM variable"))
    rows = result.fetchall()

    for variable_id, value in rows:
        string_value = str(value)
        conn.execute(
            sa.text("UPDATE variable SET string_value = :string_value WHERE id = :id"),
            {"string_value": string_value, "id": variable_id},
        )

    op.drop_column("variable", "value")
    op.alter_column("variable", "string_value", new_column_name="value", nullable=False)
