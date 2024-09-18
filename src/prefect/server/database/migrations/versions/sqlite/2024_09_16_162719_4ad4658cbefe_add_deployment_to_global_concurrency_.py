"""Add deployment to global concurrency limit FK

Revision ID: 4ad4658cbefe
Revises: 7d6350aea855
Create Date: 2024-09-16 16:27:19.451150

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "4ad4658cbefe"
down_revision = "7d6350aea855"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "concurrency_limit_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__concurrency_limit_id__concurrency_limit_v2"),
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
                JOIN concurrency_limit_v2 l ON l.name = 'deployment:' || d.id
            )
            UPDATE deployment
            SET concurrency_limit_id = dlm.limit_id
            FROM deployment_limit_mapping dlm
            WHERE deployment.id = dlm.deployment_id;
    """
    )
    op.execute(sql)


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_deployment__concurrency_limit_id__concurrency_limit_v2"),
            type_="foreignkey",
        )
        batch_op.drop_column("concurrency_limit_id")
