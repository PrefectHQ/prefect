"""json_variables

Revision ID: 2ac65f1758c2
Revises: 20fbd53b3cef
Create Date: 2024-05-21 12:29:43.948758

"""

import json

import sqlalchemy as sa
from alembic import op

from prefect.server.utilities.database import JSON

# revision identifiers, used by Alembic.
revision = "2ac65f1758c2"
down_revision = "20fbd53b3cef"
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

    with op.batch_alter_table("variable") as batch_op:
        batch_op.drop_column("value")
        batch_op.alter_column("json_value", new_column_name="value")


def downgrade():
    op.add_column("variable", sa.Column("string_value", sa.String, nullable=True))

    conn = op.get_bind()

    result = conn.execute(sa.text("SELECT id, value FROM variable"))
    rows = result.fetchall()

    for variable_id, value in rows:
        string_value = json.loads(str(value))
        conn.execute(
            sa.text("UPDATE variable SET string_value = :string_value WHERE id = :id"),
            {"string_value": string_value, "id": variable_id},
        )

    with op.batch_alter_table("variable") as batch_op:
        batch_op.drop_column("value")
        batch_op.alter_column("string_value", new_column_name="value", nullable=False)
