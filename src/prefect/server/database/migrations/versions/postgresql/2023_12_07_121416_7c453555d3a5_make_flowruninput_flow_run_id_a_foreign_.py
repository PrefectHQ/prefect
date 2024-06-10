"""Make `FlowRunInput.flow_run_id` a foreign key to `flow_run`

Revision ID: 7c453555d3a5
Revises: 733ca1903976
Create Date: 2023-12-07 12:14:16.744743

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7c453555d3a5"
down_revision = "733ca1903976"
branch_labels = None
depends_on = None


def upgrade():
    op.create_foreign_key(
        op.f("fk_flow_run_input__flow_run_id__flow_run"),
        "flow_run_input",
        "flow_run",
        ["flow_run_id"],
        ["id"],
        ondelete="cascade",
    )


def downgrade():
    op.drop_constraint(
        op.f("fk_flow_run_input__flow_run_id__flow_run"),
        "flow_run_input",
        type_="foreignkey",
    )
