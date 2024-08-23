"""add job config to flow run

Revision ID: 512343402e7d
Revises: f93e1439f022
Create Date: 2024-08-21 11:25:02.594239

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "512343402e7d"
down_revision = "f93e1439f022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flow_run_infrastructure_configuration",
        sa.Column(
            "flow_run_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.Column(
            "job_configuration",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
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
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_flow_run_infrastructure_configuration")
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.id"],
            name=op.f(
                "fk_flow_run_infrastructure_configuration__flow_run_id__flow_run"
            ),
            ondelete="CASCADE",
        ),
    )
    with op.batch_alter_table(
        "flow_run_infrastructure_configuration", schema=None
    ) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_flow_run_infrastructure_configuration__flow_run_id"),
            ["flow_run_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_flow_run_infrastructure_configuration__updated"),
            ["updated"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table(
        "flow_run_infrastructure_configuration", schema=None
    ) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_flow_run_infrastructure_configuration__updated")
        )
        batch_op.drop_index(
            batch_op.f("ix_flow_run_infrastructure_configuration__flow_run_id")
        )

    op.drop_table("flow_run_infrastructure_configuration")
