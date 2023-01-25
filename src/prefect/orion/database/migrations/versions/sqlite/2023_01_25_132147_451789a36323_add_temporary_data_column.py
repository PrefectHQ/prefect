"""Create temporary _data column

Revision ID: 451789a36323
Revises: bb38729c471a
Create Date: 2023-01-25 13:21:47.389352

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '451789a36323'
down_revision = 'bb38729c471a'
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
