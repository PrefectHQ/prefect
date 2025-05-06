"""add scope+leader idx to AutomationEventFollower

Revision ID: 1c9bb7f78263
Revises: 4160a4841eed
Create Date: 2025-05-04 19:32:49.195966

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "1c9bb7f78263"
down_revision = "4160a4841eed"
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
