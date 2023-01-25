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
    op.add_column('flow_run_state', sa.Column('_data', sa.JSON(), nullable=True))
    op.add_column('task_run_state', sa.Column('_data', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('task_run_state', '_data')
    op.drop_column('flow_run_state', '_data')
