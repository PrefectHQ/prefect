"""Make `FlowRunInput.flow_run_id` a foreign key to `flow_run`

Revision ID: 35659cc49969
Revises: a299308852a7
Create Date: 2023-12-07 12:16:24.287059

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "35659cc49969"
down_revision = "a299308852a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run_input", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run_input__flow_run_id__flow_run"),
            "flow_run",
            ["flow_run_id"],
            ["id"],
            ondelete="cascade",
        )


def downgrade():
    with op.batch_alter_table("flow_run_input", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_flow_run_input__flow_run_id__flow_run"), type_="foreignkey"
        )
