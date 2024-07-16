"""Adding scope to followers

Revision ID: 7495a5013e7e
Revises: 94622c1663e8
Create Date: 2024-07-15 14:52:40.850932

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7495a5013e7e"
down_revision = "94622c1663e8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "automation_event_follower", sa.Column("scope", sa.String(), nullable=False)
    )
    op.drop_constraint(
        "uq_automation_event_follower__follower_event_id",
        "automation_event_follower",
        type_="unique",
    )
    op.create_index(
        op.f("ix_automation_event_follower__scope"),
        "automation_event_follower",
        ["scope"],
        unique=False,
    )
    op.create_index(
        "uq_follower_for_scope",
        "automation_event_follower",
        ["scope", "follower_event_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_follower_for_scope", table_name="automation_event_follower")
    op.drop_index(
        op.f("ix_automation_event_follower__scope"),
        table_name="automation_event_follower",
    )
    op.create_unique_constraint(
        "uq_automation_event_follower__follower_event_id",
        "automation_event_follower",
        ["follower_event_id"],
    )
    op.drop_column("automation_event_follower", "scope")
