"""Add concurrency_limit_v2.used_for column

Revision ID: 1546a8d9a8f7
Revises: 97429116795e
Create Date: 2024-09-06 16:52:10.838173

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1546a8d9a8f7"
down_revision = "97429116795e"
branch_labels = None
depends_on = None


def upgrade():
    concurrency_limit_used_for_enum = postgresql.ENUM(
        "DEPLOYMENT_CONCURRENCY_LIMITING", name="concurrency_limit_used_for"
    )
    concurrency_limit_used_for_enum.create(op.get_bind())

    op.add_column(
        "concurrency_limit_v2",
        sa.Column(
            "used_for",
            sa.Enum(
                "DEPLOYMENT_CONCURRENCY_LIMITING", name="concurrency_limit_used_for"
            ),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_concurrency_limit_v2__used_for"),
        "concurrency_limit_v2",
        ["used_for"],
        unique=False,
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE concurrency_limit_v2 
            SET used_for = 'DEPLOYMENT_CONCURRENCY_LIMITING'
            WHERE name LIKE 'deployment:%'
        """
        )
    )


def downgrade():
    op.drop_index(
        op.f("ix_concurrency_limit_v2__used_for"), table_name="concurrency_limit_v2"
    )
    op.drop_column("concurrency_limit_v2", "used_for")
