"""remove_flowrun_deployment_fk

Revision ID: 7d918a392297
Revises: cfdfec5d7557
Create Date: 2023-03-01 15:46:51.575837

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7d918a392297"
down_revision = "cfdfec5d7557"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            ALTER TABLE flow_run DROP CONSTRAINT IF EXISTS fk_flow_run__deployment_id__deployment
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            ALTER TABLE flow_run ADD CONSTRAINT fk_flow_run__deployment_id__deployment FOREIGN KEY(deployment_id) REFERENCES deployment (id) ON DELETE SET NULL;
            """
        )
