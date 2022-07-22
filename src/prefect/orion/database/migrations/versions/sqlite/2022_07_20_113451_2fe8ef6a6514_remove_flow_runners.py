"""Remove flow runners

Revision ID: 2fe8ef6a6514
Revises: 628a873f0d1a
Create Date: 2022-07-20 11:34:51.903172

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = "2fe8ef6a6514"
down_revision = "628a873f0d1a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("flow_runner_type")
        batch_op.drop_column("flow_runner_config")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__flow_runner_type")
        batch_op.drop_column("flow_runner_type")
        batch_op.drop_column("empirical_config")
        batch_op.drop_column("flow_runner_config")

    op.execute("PRAGMA foreign_keys=ON")

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("flow_runner_config", sqlite.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "empirical_config",
                sqlite.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("flow_runner_type", sa.VARCHAR(), nullable=True))
        batch_op.create_index(
            "ix_flow_run__flow_runner_type", ["flow_runner_type"], unique=False
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("flow_runner_config", sqlite.JSON(), nullable=True)
        )
        batch_op.add_column(sa.Column("flow_runner_type", sa.VARCHAR(), nullable=True))
