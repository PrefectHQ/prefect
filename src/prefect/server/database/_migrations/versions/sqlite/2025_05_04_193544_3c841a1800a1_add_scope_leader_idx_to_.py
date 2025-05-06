"""add scope+leader idx to AutomationEventFollower

Revision ID: 3c841a1800a1
Revises: 7655f31c5157
Create Date: 2025-05-04 19:35:44.726368

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "3c841a1800a1"
down_revision = "7655f31c5157"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        index_name="ix_ae_follower_scope_leader",
        table_name="automation_event_follower",
        columns=["scope", "leader_event_id"],
    )


def downgrade():
    op.drop_index(index_name="ix_ae_follower_scope_leader")
