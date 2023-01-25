"""Create temporary _data column

Revision ID: 9b53afa4c331
Revises: d481d5058a19
Create Date: 2023-01-25 13:20:56.808015

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9b53afa4c331'
down_revision = 'd481d5058a19'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('flow_run_state', schema=None) as batch_op:
        batch_op.add_column(sa.Column('_data', sa.JSON(), nullable=True))

    with op.batch_alter_table('task_run_state', schema=None) as batch_op:
        batch_op.add_column(sa.Column('_data', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('task_run_state', schema=None) as batch_op:
        batch_op.drop_column('_data')

    with op.batch_alter_table('flow_run_state', schema=None) as batch_op:
        batch_op.drop_column('_data')
