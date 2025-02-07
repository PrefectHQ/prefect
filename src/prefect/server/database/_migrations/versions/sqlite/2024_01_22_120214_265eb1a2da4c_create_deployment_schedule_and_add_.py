"""Create `deployment_schedule` and add `Deployment.paused`

Revision ID: 265eb1a2da4c
Revises: c63a0a6dc787
Create Date: 2024-01-22 12:02:14.583544

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "265eb1a2da4c"
down_revision = "c63a0a6dc787"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.create_table(
        "deployment_schedule",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_deployment_schedule__deployment_id"),
            ["deployment_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_deployment_schedule__updated"), ["updated"], unique=False
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("paused", sa.Boolean(), server_default="0", nullable=False)
        )
        batch_op.create_index(
            batch_op.f("ix_deployment__paused"), ["paused"], unique=False
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
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployment__paused"))
        batch_op.drop_column("paused")

    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.drop_constraint("fk_deployment_schedule__deployment_id__deployment")
        batch_op.drop_index(batch_op.f("ix_deployment_schedule__updated"))
        batch_op.drop_index(batch_op.f("ix_deployment_schedule__deployment_id"))

    op.drop_table("deployment_schedule")
    op.execute("PRAGMA foreign_keys=ON")
