"""Create new deployment version table

Revision ID: 06b7c293bc69
Revises: b5f5644500d2
Create Date: 2025-03-19 14:50:33.897448

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "06b7c293bc69"
down_revision = "b5f5644500d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deployment_version",
        sa.Column(
            "deployment_id",
            prefect.server.utilities.database.UUID(),
            nullable=False,
        ),
        sa.Column("branch", sa.String(), nullable=True),
        sa.Column(
            "version_info",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "labels",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("entrypoint", sa.String(), nullable=True),
        sa.Column(
            "pull_steps",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "parameters",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "parameter_openapi_schema",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "enforce_parameter_schema", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column(
            "work_queue_id",
            prefect.server.utilities.database.UUID(),
            nullable=True,
        ),
        sa.Column("work_queue_name", sa.String(), nullable=True),
        sa.Column(
            "infra_overrides",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["deployment_id"],
            ["deployment.id"],
            name=op.f("fk_deployment_version__deployment_id__deployment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_queue_id"],
            ["work_queue.id"],
            name=op.f("fk_deployment_version__work_queue_id__work_queue"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_version")),
    )
    op.create_index(
        op.f("ix_deployment_version__deployment_id"),
        "deployment_version",
        ["deployment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployment_version__updated"),
        "deployment_version",
        ["updated"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployment_version__work_queue_id"),
        "deployment_version",
        ["work_queue_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployment_version__work_queue_name"),
        "deployment_version",
        ["work_queue_name"],
        unique=False,
    )
    op.create_index(
        "uq_deployment_version__deployment__branch",
        "deployment_version",
        ["deployment_id", "branch"],
        unique=True,
    )

    ## alter deployment table to store references to new table
    op.add_column(
        "deployment",
        sa.Column(
            "version_id",
            prefect.server.utilities.database.UUID(),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_deployment__version_id"),
        "deployment",
        ["version_id"],
        unique=False,
    )


def downgrade():
    with op.batch_alter_table("deployment_version", schema=None) as batch_op:
        batch_op.drop_index("uq_deployment_version__deployment__branch")
        batch_op.drop_index(batch_op.f("ix_deployment_version__work_queue_name"))
        batch_op.drop_index(batch_op.f("ix_deployment_version__work_queue_id"))
        batch_op.drop_index(batch_op.f("ix_deployment_version__updated"))
        batch_op.drop_index(batch_op.f("ix_deployment_version__deployment_id"))

    # deployment table changes
    op.drop_index(op.f("ix_deployment__version_id"), table_name="deployment")
    op.drop_column("deployment", "version_id")

    op.drop_table("deployment_version")
