"""Add `bucketing_key` to `composite_trigger_child_firing`

Revision ID: b7c3f1a9d2e4
Revises: e7f54680bce3
Create Date: 2026-10-23 00:00:00.000000

Lets composite triggers group child firings by a resolved `for_each` key instead of
by timing alone.  Existing firings default to an empty key, preserving the prior
behaviour where all firings for a child share a single group.
"""

import sqlalchemy as sa
from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "b7c3f1a9d2e4"
down_revision = "e7f54680bce3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "composite_trigger_child_firing",
        sa.Column(
            "bucketing_key",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.drop_index(
        "uq_composite_trigger_child_firing__a_id__pt_id__ct__id",
        table_name="composite_trigger_child_firing",
    )
    op.create_index(
        "uq_composite_trigger_child_firing__a_id__pt_id__ct_id__bk",
        "composite_trigger_child_firing",
        ["automation_id", "parent_trigger_id", "child_trigger_id", "bucketing_key"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "uq_composite_trigger_child_firing__a_id__pt_id__ct_id__bk",
        table_name="composite_trigger_child_firing",
    )
    op.create_index(
        "uq_composite_trigger_child_firing__a_id__pt_id__ct__id",
        "composite_trigger_child_firing",
        ["automation_id", "parent_trigger_id", "child_trigger_id"],
        unique=True,
    )
    op.drop_column("composite_trigger_child_firing", "bucketing_key")
