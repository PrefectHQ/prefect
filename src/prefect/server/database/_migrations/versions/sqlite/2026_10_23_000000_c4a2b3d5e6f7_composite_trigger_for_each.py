"""Add `bucketing_key` to `composite_trigger_child_firing`

Revision ID: c4a2b3d5e6f7
Revises: 8f5eda7c1dd7
Create Date: 2026-10-23 00:00:00.000000

Lets composite triggers group child firings by a resolved `for_each` key instead of
by timing alone.  Existing firings default to an empty key, preserving the prior
behaviour where all firings for a child share a single group.
"""

import sqlalchemy as sa
from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "c4a2b3d5e6f7"
down_revision = "8f5eda7c1dd7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "composite_trigger_child_firing", schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "bucketing_key",
                prefect.server.utilities.database.JSON(astext_type=sa.Text()),
                server_default="[]",
                nullable=False,
            ),
        )
        batch_op.drop_index("uq_composite_trigger_child_firing__a_id__pt_id__ct__id")
        batch_op.create_index(
            "uq_composite_trigger_child_firing__a_id__pt_id__ct_id__bk",
            ["automation_id", "parent_trigger_id", "child_trigger_id", "bucketing_key"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table(
        "composite_trigger_child_firing", schema=None
    ) as batch_op:
        batch_op.drop_index("uq_composite_trigger_child_firing__a_id__pt_id__ct_id__bk")
        batch_op.create_index(
            "uq_composite_trigger_child_firing__a_id__pt_id__ct__id",
            ["automation_id", "parent_trigger_id", "child_trigger_id"],
            unique=True,
        )
        batch_op.drop_column("bucketing_key")
