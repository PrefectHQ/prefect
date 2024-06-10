"""Remove Artifact foreign keys

Revision ID: cfdfec5d7557
Revises: 2a88656f4a23
Create Date: 2023-02-08 15:19:58.751027

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "cfdfec5d7557"
down_revision = "2a88656f4a23"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "fk_artifact__task_run_id__task_run", "artifact", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_artifact__flow_run_id__flow_run", "artifact", type_="foreignkey"
    )


def downgrade():
    op.create_foreign_key(
        "fk_artifact__flow_run_id__flow_run",
        "artifact",
        "flow_run",
        ["flow_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_artifact__task_run_id__task_run",
        "artifact",
        "task_run",
        ["task_run_id"],
        ["id"],
    )
