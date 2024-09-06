"""Add concurrency_limit_v2.used_for column

Revision ID: b0664ac07625
Revises: f93e1439f022
Create Date: 2024-09-06 16:53:37.958335

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b0664ac07625"
down_revision = "f93e1439f022"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("concurrency_limit_v2", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "used_for",
                sa.Enum(
                    "DEPLOYMENT_CONCURRENCY_LIMITING", name="concurrency_limit_used_for"
                ),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_concurrency_limit_v2__used_for"), ["used_for"], unique=False
        )


def downgrade():
    with op.batch_alter_table("concurrency_limit_v2", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_concurrency_limit_v2__used_for"))
        batch_op.drop_column("used_for")
