"""remove_flowrun_deployment_fk

Revision ID: f3df94dca3cc
Revises: 8d148e44e669
Create Date: 2023-03-01 16:55:51.274067

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f3df94dca3cc"
down_revision = "8d148e44e669"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_flow_run__deployment_id__deployment", type_="foreignkey"
        )

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_flow_run__deployment_id__deployment",
            "deployment",
            ["deployment_id"],
            ["id"],
        )

    op.execute("PRAGMA foreign_keys=ON")
