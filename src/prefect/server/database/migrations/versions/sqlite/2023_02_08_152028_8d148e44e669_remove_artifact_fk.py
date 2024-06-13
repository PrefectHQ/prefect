"""Remove Artifact foreign keys

Revision ID: 8d148e44e669
Revises: bfe42b7090d6
Create Date: 2023-02-08 15:20:28.289591

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8d148e44e669"
down_revision = "bfe42b7090d6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_artifact__flow_run_id__flow_run", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_artifact__task_run_id__task_run", type_="foreignkey"
        )


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_artifact__task_run_id__task_run", "task_run", ["task_run_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_artifact__flow_run_id__flow_run", "flow_run", ["flow_run_id"], ["id"]
        )
