"""Create `deployment_schedule` and add `Deployment.paused`

Revision ID: 8cf4d4933848
Revises: 6b63c51c31b4
Create Date: 2024-01-22 12:06:15.096013

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "8cf4d4933848"
down_revision = "6b63c51c31b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deployment_schedule",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "schedule",
            prefect.server.utilities.database.Pydantic(
                prefect.server.schemas.schedules.SCHEDULE_TYPES
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "deployment_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["deployment_id"],
            ["deployment.id"],
            name=op.f("fk_deployment_schedule__deployment_id__deployment"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_schedule")),
    )
    op.create_index(
        op.f("ix_deployment_schedule__deployment_id"),
        "deployment_schedule",
        ["deployment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployment_schedule__updated"),
        "deployment_schedule",
        ["updated"],
        unique=False,
    )
    op.add_column(
        "deployment",
        sa.Column("paused", sa.Boolean(), server_default="0", nullable=False),
    )
    op.create_index(
        op.f("ix_deployment__paused"), "deployment", ["paused"], unique=False
    )

    backfill_schedules = """
        INSERT INTO deployment_schedule (deployment_id, schedule, active)
        SELECT
            d.id AS deployment_id,
            d.schedule,
            d.is_schedule_active AS active
        FROM
            deployment d
        WHERE
            d.schedule IS NOT NULL
            and d.schedule != 'null';
    """
    backfill_paused = """
        UPDATE deployment SET paused = NOT is_schedule_active where paused = is_schedule_active;
    """

    op.execute(sa.text(backfill_schedules))
    op.execute(sa.text(backfill_paused))


def downgrade():
    op.drop_index(op.f("ix_deployment__paused"), table_name="deployment")
    op.drop_column("deployment", "paused")
    op.drop_index(
        op.f("ix_deployment_schedule__updated"), table_name="deployment_schedule"
    )
    op.drop_index(
        op.f("ix_deployment_schedule__deployment_id"), table_name="deployment_schedule"
    )
    op.drop_table("deployment_schedule")
