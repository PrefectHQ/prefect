"""add_log_flow_run_id_and_task_run_id_fk

Revision ID: ffa2a93baefa
Revises: 3b86c5ea017a
Create Date: 2025-07-14 09:33:57.991124

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "ffa2a93baefa"
down_revision = "3b86c5ea017a"
branch_labels = None
depends_on = None


def upgrade():
    # remove rows which should have been deleted by the cascade delete
    op.execute("""
        DELETE FROM
            log
        WHERE
        (
            task_run_id IS NOT NULL
            AND NOT EXISTS (
            SELECT
                1
            FROM
                task_run
            WHERE
                task_run.id = log.task_run_id
            )
        )
        OR (
            flow_run_id IS NOT NULL
            AND NOT EXISTS (
            SELECT
                1
            FROM
                flow_run
            WHERE
                flow_run.id = log.flow_run_id
            )
        )
    """)

    # add foreign keys
    op.create_foreign_key(
        op.f("fk_log__flow_run_id__flow_run"),
        "log",
        "flow_run",
        ["flow_run_id"],
        ["id"],
        ondelete="CASCADE",
        use_alter=True,
    )
    op.create_foreign_key(
        op.f("fk_log__task_run_id__task_run"),
        "log",
        "task_run",
        ["task_run_id"],
        ["id"],
        ondelete="CASCADE",
        use_alter=True,
    )


def downgrade():
    # drop foreign keys
    op.drop_constraint(op.f("fk_log__task_run_id__task_run"), "log", type_="foreignkey")
    op.drop_constraint(op.f("fk_log__flow_run_id__flow_run"), "log", type_="foreignkey")
