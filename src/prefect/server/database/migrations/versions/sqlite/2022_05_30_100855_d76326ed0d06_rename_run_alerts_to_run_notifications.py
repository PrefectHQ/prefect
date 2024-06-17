"""Rename run alerts to run notifications

Revision ID: d76326ed0d06
Revises: 33439667aeea
Create Date: 2022-05-30 10:08:55.886326

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d76326ed0d06"
down_revision = "e73c6f1fe752"
branch_labels = None
depends_on = None


def upgrade():
    # policy table
    op.rename_table("flow_run_alert_policy", "flow_run_notification_policy")
    with op.batch_alter_table("flow_run_notification_policy") as batch_op:
        batch_op.drop_index("ix_flow_run_alert_policy__name")
        batch_op.create_index(
            op.f("ix_flow_run_notification_policy__name"),
            ["name"],
            unique=False,
        )
        batch_op.drop_index("ix_flow_run_alert_policy__updated")
        batch_op.create_index(
            op.f("ix_flow_run_notification_policy__updated"),
            ["updated"],
            unique=False,
        )
        batch_op.drop_constraint("pk_flow_run_alert")
        batch_op.create_primary_key("pk_flow_run_notification_policy", ["id"])

    # queue table
    op.rename_table("flow_run_alert_queue", "flow_run_notification_queue")
    with op.batch_alter_table("flow_run_notification_queue") as batch_op:
        batch_op.alter_column(
            "flow_run_alert_policy_id",
            new_column_name="flow_run_notification_policy_id",
        )
        batch_op.drop_index("ix_flow_run_alert_queue__updated")
        batch_op.create_index(
            op.f("ix_flow_run_notification_queue__updated"),
            ["updated"],
            unique=False,
        )
        batch_op.drop_constraint("pk_flow_run_alert_queue")
        batch_op.create_primary_key("pk_flow_run_notification_queue", ["id"])


def downgrade():
    # queue table
    op.rename_table("flow_run_notification_queue", "flow_run_alert_queue")
    with op.batch_alter_table("flow_run_alert_queue") as batch_op:
        batch_op.alter_column(
            "flow_run_notification_policy_id",
            new_column_name="flow_run_alert_policy_id",
        )
        batch_op.drop_index("ix_flow_run_notification_queue__updated")
        batch_op.create_index(
            op.f("ix_flow_run_alert_queue__updated"),
            ["updated"],
            unique=False,
        )
        batch_op.drop_constraint("pk_flow_run_notification_queue")
        batch_op.create_primary_key("pk_flow_run_alert_queue", ["id"])

    # policy table
    op.rename_table("flow_run_notification_policy", "flow_run_alert_policy")
    with op.batch_alter_table("flow_run_alert_policy") as batch_op:
        batch_op.drop_index("ix_flow_run_notification_policy__name")
        batch_op.create_index(
            op.f("ix_flow_run_alert_policy__name"),
            ["name"],
            unique=False,
        )
        batch_op.drop_index("ix_flow_run_notification_policy__updated")
        batch_op.create_index(
            op.f("ix_flow_run_alert_policy__updated"),
            ["updated"],
            unique=False,
        )
        batch_op.drop_constraint("pk_flow_run_notification_policy")
        batch_op.create_primary_key("pk_flow_run_alert", ["id"])
