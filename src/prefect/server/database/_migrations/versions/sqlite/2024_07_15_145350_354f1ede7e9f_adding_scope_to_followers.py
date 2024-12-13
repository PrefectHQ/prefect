"""Adding scope to followers

Revision ID: 354f1ede7e9f
Revises: 2ac65f1758c2
Create Date: 2024-07-15 14:53:50.718831

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "354f1ede7e9f"
down_revision = "2ac65f1758c2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("automation_event_follower", schema=None) as batch_op:
        batch_op.add_column(sa.Column("scope", sa.String(), nullable=False))
        batch_op.drop_constraint(
            "uq_automation_event_follower__follower_event_id", type_="unique"
        )
        batch_op.create_index(
            batch_op.f("ix_automation_event_follower__scope"), ["scope"], unique=False
        )
        batch_op.create_index(
            "uq_follower_for_scope", ["scope", "follower_event_id"], unique=True
        )


def downgrade():
    with op.batch_alter_table("automation_event_follower", schema=None) as batch_op:
        batch_op.drop_index("uq_follower_for_scope")
        batch_op.drop_index(batch_op.f("ix_automation_event_follower__scope"))
        batch_op.create_unique_constraint(
            "uq_automation_event_follower__follower_event_id", ["follower_event_id"]
        )
        batch_op.drop_column("scope")
