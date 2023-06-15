"""Add infra_overrides to FlowRun table

Revision ID: f33c7f8c041d
Revises: 2dbcec43c857
Create Date: 2023-06-15 17:24:12.714786

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'f33c7f8c041d'
down_revision = '2dbcec43c857'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('flow_run', schema=None) as batch_op:
        batch_op.add_column(sa.Column('infra_overrides', sqlite.JSON(), server_default="{}", nullable=False))

def downgrade():

    with op.batch_alter_table('flow_run', schema=None) as batch_op:
        batch_op.drop_column('infra_overrides')