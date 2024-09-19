"""Add deployment to global concurrency limit FK

Revision ID: eaec5004771f
Revises: 555ed31b284d
Create Date: 2024-09-16 15:20:51.582204

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "eaec5004771f"
down_revision = "555ed31b284d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column(
            "concurrency_limit_id",
            prefect.server.utilities.database.UUID(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        op.f("fk_deployment__concurrency_limit_id__concurrency_limit_v2"),
        "deployment",
        "concurrency_limit_v2",
        ["concurrency_limit_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # migrate existing data
    sql = sa.text(
        """
        WITH deployment_limit_mapping AS (
            SELECT d.id AS deployment_id, l.id AS limit_id
            FROM deployment d
            JOIN concurrency_limit_v2 l ON l.name = 'deployment:' || d.id::text
        )
        UPDATE deployment
        SET concurrency_limit_id = dlm.limit_id
        FROM deployment_limit_mapping dlm
        WHERE deployment.id = dlm.deployment_id;
    """
    )
    op.execute(sql)


def downgrade():
    op.drop_constraint(
        op.f("fk_deployment__concurrency_limit_id__concurrency_limit_v2"),
        "deployment",
        type_="foreignkey",
    )
    op.drop_column("deployment", "concurrency_limit_id")
